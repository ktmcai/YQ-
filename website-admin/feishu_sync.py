import hashlib
import os
import sqlite3
import tempfile
import threading
import warnings
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4

from flask import abort, jsonify, request
from PIL import Image
from pypdf import PdfReader

from feishu import FeishuClient, Renderer, SOURCES, SyncError, document_url
from taxonomy import guide_categories, guide_location


def source_map(connection):
    return {row['slug']: dict(row) for row in connection.execute(
        'SELECT s.*,g.published FROM guide_sources s JOIN guides g ON g.slug=s.slug')}


class Assets:
    def __init__(self, client, folder, staging, slug, existing):
        self.client, self.folder, self.staging, self.slug = client, folder, staging, slug
        self.existing = existing
        self.new = []
        self.cache = {}
        self.hashes = {}
        self.total = 0

    def __call__(self, token, name, image, board):
        key = (token, name, image, board)
        if key in self.cache:
            return self.cache[key]
        identifier = uuid4().hex
        path = self.staging / identifier
        self.client.download(token, path, board)
        size = path.stat().st_size
        self.total += size
        if self.total > 600 * 1024 * 1024:
            raise SyncError('本份资料附件总大小超过 600 MB，本次未发布。')
        name = ''.join(c for c in name.replace('\\', '/').split('/')[-1] if ord(c) >= 32 and ord(c) != 127)[:180] or '附件'
        width = height = None
        media_type = 'application/octet-stream'
        if image:
            with warnings.catch_warnings():
                warnings.simplefilter('error', Image.DecompressionBombWarning)
                with Image.open(path) as picture:
                    width, height = picture.size
                    extension, media_type = {'PNG': ('.png', 'image/png'), 'JPEG': ('.jpg', 'image/jpeg'), 'GIF': ('.gif', 'image/gif'), 'WEBP': ('.webp', 'image/webp')}[picture.format]
                    picture.verify()
            name = ('画板' if board else '图片') + extension
        else:
            extension = Path(name).suffix.lower()
            if extension not in ('.pdf', '.zip', '.stp', '.step', '.json', '.bin', '.hex'):
                raise SyncError('附件格式暂不支持：' + name + '，本次未发布。')
            if extension == '.pdf':
                with path.open('rb') as stream:
                    pdf = PdfReader(stream)
                    if pdf.is_encrypted or not len(pdf.pages):
                        raise SyncError('PDF 附件无法在线查看：' + name)
                media_type = 'application/pdf'
        with path.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        resource = None
        for item in self.existing:
            if item['byte_size'] != size or item['media_type'] != media_type or (not image and item['original_name'] != name):
                continue
            old_file = self.folder / item['stored_name']
            if not old_file.is_file():
                continue
            if item['id'] not in self.hashes:
                with old_file.open('rb') as stream:
                    self.hashes[item['id']] = hashlib.file_digest(stream, 'sha256').hexdigest()
            if self.hashes[item['id']] == digest:
                resource = item['public_url']
                break
        if resource is None:
            stored_name = identifier + extension
            resource = quote(f'/guides/{self.slug}/assets/{identifier}/{name}', safe='/')
            self.new.append({'id': identifier, 'guide_slug': self.slug, 'public_url': resource, 'stored_name': stored_name,
                             'original_name': name, 'media_type': media_type, 'byte_size': size, 'path': path})
        self.cache[key] = resource, width, height
        return self.cache[key]


def publish(connection, job_id, guide, title, content, text, assets, references, stats, folder):
    moved = []
    try:
        with connection:
            connection.execute('BEGIN IMMEDIATE')
            job = connection.execute('SELECT status FROM guide_sync_jobs WHERE id=?', (job_id,)).fetchone()
            current = connection.execute('SELECT version FROM guides WHERE slug=?', (guide['slug'],)).fetchone()
            if not job or job['status'] != 'running':
                raise SyncError('同步任务已中断，本次未发布。')
            if not current or current['version'] != guide['version']:
                raise SyncError('网站资料在同步期间被修改，已保留网站修改，请刷新后重试。')
            if content == guide['content_html'] and title == guide['title']:
                message = '飞书内容与官网一致，无需更新。'
            else:
                if guide['published']:
                    connection.execute('INSERT INTO guide_sync_history (job_id,slug,title,content_html,search_text,version) VALUES (?,?,?,?,?,?)',
                                       (job_id, guide['slug'], guide['title'], guide['content_html'], guide['search_text'], guide['version']))
                for item in assets:
                    target = folder / item['stored_name']
                    item['path'].replace(target)
                    moved.append(target)
                    connection.execute('INSERT INTO guide_assets (id,guide_slug,public_url,stored_name,original_name,media_type,byte_size) VALUES (?,?,?,?,?,?,?)',
                                       tuple(item[k] for k in ('id', 'guide_slug', 'public_url', 'stored_name', 'original_name', 'media_type', 'byte_size')))
                connection.execute('UPDATE guides SET title=?,content_html=?,search_text=?,published=1,version=version+1,updated_at=CURRENT_TIMESTAMP WHERE slug=?', (title, content, text, guide['slug']))
                from guides import update_asset_references
                update_asset_references(connection, guide['slug'], references)
                message = f'已同步并发布：{stats["headings"]} 个章节、{stats["images"] + stats["boards"]} 张图片、{stats["tables"]} 张表格、{stats["files"]} 个附件。'
            connection.execute("UPDATE guide_sync_jobs SET status='succeeded',message=?,finished_at=CURRENT_TIMESTAMP WHERE id=?", (message, job_id))
    except Exception:
        for path in moved:
            path.unlink(missing_ok=True)
        raise


def sync_document(app, job_id):
    from guides import prepare_content
    data = Path(app.config['DATA_DIR'])
    connection = sqlite3.connect(data / 'documents.sqlite', timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute('PRAGMA foreign_keys=ON')
    try:
        job = connection.execute('SELECT * FROM guide_sync_jobs WHERE id=?', (job_id,)).fetchone()
        guide = dict(connection.execute('SELECT * FROM guides WHERE slug=?', (job['slug'],)).fetchone())
        if guide['version'] != job['base_version']:
            raise SyncError('网站资料已更新，请刷新后重新同步。')
        client = FeishuClient(app.config['FEISHU_APP_ID'], app.config['FEISHU_APP_SECRET'])
        sources = source_map(connection)
        meta, blocks = client.document(sources[guide['slug']])
        folder = data / 'guide-files'
        with tempfile.TemporaryDirectory(prefix='.sync-', dir=folder) as staging:
            existing = connection.execute('SELECT * FROM guide_assets WHERE guide_slug=?', (guide['slug'],)).fetchall()
            assets = Assets(client, folder, Path(staging), guide['slug'], existing)
            renderer = Renderer(client, meta, blocks, assets, guide['content_html'], guide['slug'], sources)
            content, text, references = prepare_content(renderer.render())
            if len(content.encode()) > 1024 * 1024:
                raise SyncError('转换后正文超过 1 MB，本次未发布。')
            known = {row['public_url'] for row in connection.execute('SELECT public_url FROM guide_assets')} | {a['public_url'] for a in assets.new}
            if not references <= known:
                raise SyncError('正文包含无法获取的图片或附件，本次未发布。')
            client.verify_revision(meta)
            publish(connection, job_id, guide, meta['title'], content, text, assets.new, references, renderer.stats, folder)
    except Exception as problem:
        message = str(problem) if isinstance(problem, SyncError) else '同步校验失败，官网内容未更新，请联系维护人员检查。'
        # Do not include remote payloads or credentials in logs or job messages.
        app.logger.warning('Feishu sync %s failed (%s)', job_id, type(problem).__name__)
        with connection:
            connection.execute("UPDATE guide_sync_jobs SET status='failed',message=?,finished_at=CURRENT_TIMESTAMP WHERE id=? AND status='running'", (message, job_id))
    finally:
        connection.close()


def register_sync(app, db, guides):
    app.config.setdefault('FEISHU_APP_ID', os.environ.get('YONIQ_FEISHU_APP_ID', ''))
    app.config.setdefault('FEISHU_APP_SECRET', os.environ.get('YONIQ_FEISHU_APP_SECRET', ''))
    with app.app_context():
        db().executescript('''
            CREATE TABLE IF NOT EXISTS guide_sources (
                slug TEXT PRIMARY KEY REFERENCES guides(slug), url TEXT NOT NULL UNIQUE,
                document_id TEXT NOT NULL UNIQUE
            );
            CREATE TABLE IF NOT EXISTS guide_sync_jobs (
                id TEXT PRIMARY KEY, slug TEXT NOT NULL REFERENCES guides(slug), base_version INTEGER NOT NULL,
                status TEXT NOT NULL, message TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                finished_at TEXT
            );
            CREATE UNIQUE INDEX IF NOT EXISTS guide_sync_single_active ON guide_sync_jobs(status) WHERE status='running';
            CREATE TABLE IF NOT EXISTS guide_sync_history (
                job_id TEXT PRIMARY KEY REFERENCES guide_sync_jobs(id), slug TEXT NOT NULL REFERENCES guides(slug),
                title TEXT NOT NULL, content_html TEXT NOT NULL, search_text TEXT NOT NULL, version INTEGER NOT NULL
            );
        ''')
        # Deployment uses one Gunicorn worker. A restarted worker cannot resume its former thread.
        with db():
            for slug, source in SOURCES.items():
                db().execute('INSERT OR IGNORE INTO guide_sources(slug,url,document_id) SELECT slug,?,? FROM guides WHERE slug=?',
                             (source['url'], source['document_id'], slug))
            db().execute("UPDATE guide_sync_jobs SET status='failed',message='服务重启中断了同步，请重新同步。',finished_at=CURRENT_TIMESTAMP WHERE status='running'")

    @app.context_processor
    def sync_context():
        if request.endpoint not in ('guides.listing', 'guides.edit'):
            return {}
        latest = db().execute('SELECT * FROM guide_sync_jobs WHERE rowid IN (SELECT MAX(rowid) FROM guide_sync_jobs GROUP BY slug)').fetchall()
        return {'feishu_sources': source_map(db()), 'guide_categories': guide_categories(db()),
                'sync_ready': bool(app.config['FEISHU_APP_ID'] and app.config['FEISHU_APP_SECRET']),
                'sync_jobs': {job['slug']: dict(job) for job in latest}, 'sync_running': any(job['status'] == 'running' for job in latest)}

    def launch(identifier):
        try:
            threading.Thread(target=sync_document, args=(app, identifier), daemon=True).start()
        except RuntimeError:
            with db():
                db().execute("UPDATE guide_sync_jobs SET status='failed',message='同步未能启动，请稍后重试。',finished_at=CURRENT_TIMESTAMP WHERE id=?", (identifier,))
            return jsonify(error='同步未能启动，请刷新列表后重试。'), 503
        return jsonify(id=identifier, status='running'), 202

    @guides.post('/admin/guides/import')
    def import_document():
        if not app.config['FEISHU_APP_ID'] or not app.config['FEISHU_APP_SECRET']:
            return jsonify(error='飞书连接尚未配置。'), 503
        try:
            url = document_url(request.form.get('url', ''))
            classification = request.form.get('category', '通用资料')
            if classification not in guide_categories(db()):
                raise SyncError('请选择列表中的文档分类。')
            category, series = guide_location(classification)
            if db().execute("SELECT 1 FROM guide_sync_jobs WHERE status='running'").fetchone():
                return jsonify(error='已有资料正在同步，请等待完成后再导入。'), 409
            client = FeishuClient(app.config['FEISHU_APP_ID'], app.config['FEISHU_APP_SECRET'])
            document_id = client.resolve(url)
            existing = db().execute('SELECT slug FROM guide_sources WHERE document_id=?', (document_id,)).fetchone()
            if existing:
                return jsonify(error='这份飞书资料已在列表中，请使用原条目的同步按钮。', existing_url='/admin/guides#guide-' + existing['slug']), 409
            meta = client.metadata(document_id)
            title = meta['title'].strip() or '未命名文档'
            slug, identifier = 'feishu-' + uuid4().hex[:16], uuid4().hex
            with db():
                db().execute('BEGIN IMMEDIATE')
                # Leave room beside the chosen category so the public sidebar stays grouped.
                order = db().execute('SELECT MAX(sort_order) FROM guides WHERE category=?', (category,)).fetchone()[0]
                if order is None:
                    order = db().execute('SELECT COALESCE(MAX(sort_order),0) FROM guides').fetchone()[0]
                db().execute('UPDATE guides SET sort_order=sort_order+1 WHERE sort_order>?', (order,))
                db().execute("INSERT INTO guides(slug,title,label,category,sort_order,series,content_html,search_text,version,published) VALUES (?,?,?,?,?,?,'','',0,0)",
                             (slug, title, title[:120], category, order + 1, series))
                db().execute('INSERT INTO guide_sources(slug,url,document_id) VALUES (?,?,?)', (slug, url, document_id))
                db().execute("INSERT INTO guide_sync_jobs(id,slug,base_version,status,message) VALUES (?,?,0,'running','正在导入，完整校验通过后才会在官网显示…')", (identifier, slug))
            response, status = launch(identifier)
            if status == 202:
                response = jsonify(id=identifier, status='running', location='/admin/guides/?imported=' + slug + '#guide-' + slug)
            return response, status
        except SyncError as problem:
            return jsonify(error=str(problem)), 400
        except sqlite3.IntegrityError:
            return jsonify(error='这份资料已被导入，或另一个同步任务刚刚启动，请刷新列表查看。'), 409

    @guides.post('/admin/guides/<slug>/sync')
    def sync(slug):
        if not db().execute('SELECT 1 FROM guide_sources WHERE slug=?', (slug,)).fetchone():
            abort(404)
        if not app.config['FEISHU_APP_ID'] or not app.config['FEISHU_APP_SECRET']:
            return jsonify(error='飞书连接尚未配置。'), 503
        guide = db().execute('SELECT * FROM guides WHERE slug=?', (slug,)).fetchone()
        if not guide:
            abort(404)
        if request.form.get('version') != str(guide['version']):
            return jsonify(error='网站资料已更新，请刷新后重试。'), 409
        identifier = uuid4().hex
        try:
            with db():
                db().execute("INSERT INTO guide_sync_jobs (id,slug,base_version,status,message) VALUES (?,?,?,'running','正在读取飞书并下载图片、表格和附件…')", (identifier, slug, guide['version']))
        except sqlite3.IntegrityError:
            return jsonify(error='已有资料正在同步，请等待完成后再操作。'), 409
        return launch(identifier)

    @guides.get('/admin/guides/sync-status')
    def sync_status():
        rows = db().execute('SELECT id,slug,status,message,created_at,finished_at FROM guide_sync_jobs WHERE rowid IN (SELECT MAX(rowid) FROM guide_sync_jobs GROUP BY slug)').fetchall()
        return jsonify(jobs=[dict(row) for row in rows])
