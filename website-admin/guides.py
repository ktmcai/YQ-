import html
import re
import tempfile
import warnings
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlsplit
from uuid import uuid4

import nh3
from PIL import Image, UnidentifiedImageError
from pypdf import PdfReader
from pypdf.errors import PdfReadError
from flask import Blueprint, abort, flash, g, jsonify, redirect, render_template, request, send_file, url_for
from taxonomy import AXIS, AXIS_SERIES, guide_categories, guide_location


def asset_url(value):
    parsed = urlsplit(value)
    if parsed.scheme or parsed.netloc:
        return None
    if parsed.path == '/vendor/pdfjs-6.4.299-legacy/web/viewer.html':
        return asset_url(parse_qs(parsed.query).get('file', [''])[0])
    if parsed.path.startswith('/guides/'):
        return quote(unquote(parsed.path), safe='/')
    return None


def safe_attribute(tag, name, value):
    if name == 'id':
        return value if tag in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6') and re.fullmatch(r'section-[A-Za-z0-9_-]+', value) else None
    if name in ('href', 'src'):
        if re.search(r'[\x00-\x20\x7f\\]', value):
            return None
        try:
            parsed = urlsplit(value)
            if parsed.username or parsed.password or value.startswith('//'):
                return None
            if name == 'src':
                return asset_url(value)
            if value.startswith(('/', '#')) or (parsed.scheme in ('http', 'https') and parsed.hostname) or (parsed.scheme == 'mailto' and parsed.path):
                return value
        except ValueError:
            pass
        return None
    if name in ('width', 'height', 'rowspan', 'colspan', 'start'):
        return value if re.fullmatch(r'[1-9]\d{0,4}', value) else None
    if name == 'target':
        return '_blank' if value == '_blank' else None
    return value


class GuideHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.output = []
        self.text = []
        self.assets = set()
        self.ids = set()

    def handle_starttag(self, tag, attrs):
        if tag == 'h1':
            tag = 'h2'
        attrs = dict(attrs)
        if tag in ('h2', 'h3', 'h4', 'h5', 'h6'):
            identifier = attrs.get('id')
            if not identifier or identifier in self.ids:
                identifier = 'section-' + uuid4().hex[:12]
            attrs['id'] = identifier
            self.ids.add(identifier)
        for name in ('href', 'src'):
            if name in attrs:
                resource = asset_url(attrs[name])
                if resource:
                    self.assets.add(resource)
        attributes = ''.join(f' {name}="{html.escape(value or "", quote=True)}"' for name, value in attrs.items())
        self.output.append(f'<{tag}{attributes}>')
        if tag == 'br':
            self.text.append(' ')

    def handle_endtag(self, tag):
        self.output.append(f'</{"h2" if tag == "h1" else tag}>')
        if tag not in ('strong', 'b', 'em', 'i', 'u', 's', 'span', 'a', 'code', 'sub', 'sup'):
            self.text.append(' ')

    def handle_data(self, data):
        self.output.append(html.escape(data, quote=False))
        self.text.append(data)


def prepare_content(content):
    cleaned = nh3.clean(
        content,
        tags=set('p br div span h1 h2 h3 h4 h5 h6 strong b em i u s sub sup ul ol li a img table caption thead tbody tfoot tr th td pre code blockquote hr colgroup col'.split()),
        attributes={
            '*': {'id', 'style'}, 'a': {'href', 'target', 'title', 'download'},
            'img': {'src', 'alt', 'width', 'height', 'loading', 'decoding'},
            'td': {'rowspan', 'colspan'}, 'th': {'rowspan', 'colspan', 'scope'},
            'ol': {'start'}, 'div': {'role', 'aria-label', 'tabindex'},
        },
        allowed_classes={'div': {'table-scroll', 'feishu-document', 'feishu-columns', 'feishu-column'},
                         'table': {'feishu-table', 'feishu-sheet'}, 'a': {'attachment-download'}},
        attribute_filter=safe_attribute,
        url_schemes={'http', 'https', 'mailto'},
        filter_style_properties={'text-align', 'width', 'height', 'max-width', 'font-family', 'font-size', 'font-weight', 'font-style', 'text-decoration', 'color', 'background-color', 'vertical-align'},
    )
    parsed = GuideHTML()
    parsed.feed(cleaned)
    return ''.join(parsed.output), re.sub(r'\s+', ' ', ''.join(parsed.text)).strip(), parsed.assets


def update_asset_references(connection, slug, assets):
    connection.execute('DELETE FROM guide_asset_refs WHERE guide_slug=?', (slug,))
    for resource in assets:
        connection.execute('INSERT OR IGNORE INTO guide_asset_refs (guide_slug,asset_id) SELECT ?,id FROM guide_assets WHERE public_url=?', (slug, resource))


def register_guides(app, db):
    guides = Blueprint('guides', __name__)
    files_dir = Path(app.config['DATA_DIR']) / 'guide-files'
    files_dir.mkdir(parents=True, exist_ok=True)
    with app.app_context():
        db().executescript('''
            CREATE TABLE IF NOT EXISTS guides (
                slug TEXT PRIMARY KEY, title TEXT NOT NULL, label TEXT NOT NULL,
                category TEXT NOT NULL, sort_order INTEGER NOT NULL,
                content_html TEXT NOT NULL, search_text TEXT NOT NULL,
                version INTEGER NOT NULL DEFAULT 1,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS guide_assets (
                id TEXT PRIMARY KEY, guide_slug TEXT NOT NULL REFERENCES guides(slug),
                public_url TEXT NOT NULL UNIQUE, stored_name TEXT NOT NULL UNIQUE,
                original_name TEXT NOT NULL, media_type TEXT NOT NULL, byte_size INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS guide_asset_refs (
                guide_slug TEXT NOT NULL REFERENCES guides(slug),
                asset_id TEXT NOT NULL REFERENCES guide_assets(id),
                PRIMARY KEY (guide_slug,asset_id)
            );
            CREATE TABLE IF NOT EXISTS guide_migrations (name TEXT PRIMARY KEY);
        ''')
        if 'published' not in {row['name'] for row in db().execute('PRAGMA table_info(guides)')}:
            with db():
                db().execute('ALTER TABLE guides ADD COLUMN published INTEGER NOT NULL DEFAULT 1')
        if 'series' not in {row['name'] for row in db().execute('PRAGMA table_info(guides)')}:
            with db():
                db().execute("ALTER TABLE guides ADD COLUMN series TEXT NOT NULL DEFAULT ''")
                for branch in AXIS_SERIES:
                    db().execute('UPDATE guides SET series=? WHERE category=? AND (UPPER(label) LIKE ? OR UPPER(title) LIKE ?)', (branch['code'], AXIS, branch['code'] + '%', AXIS + ' ' + branch['code'] + '%'))

    def guide(slug):
        item = db().execute('SELECT * FROM guides WHERE slug=?', (slug,)).fetchone()
        if not item or not item['published']:
            abort(404, description='这份在线文档不存在。')
        return item

    @guides.get('/admin/guides', strict_slashes=False)
    def listing():
        return render_template('guides.html', guides=db().execute('SELECT * FROM guides ORDER BY sort_order,slug').fetchall())

    @guides.route('/admin/guides/<slug>/edit', methods=['GET', 'POST'])
    def edit(slug):
        item = guide(slug)
        values = dict(item)
        values['classification'] = item['category'] + (' / ' + item['series'] if item['series'] else '')
        error = None
        status = 200
        if request.method == 'POST':
            values.update({key: request.form.get(key, '') for key in ('title', 'label', 'content_html', 'version')})
            values['classification'] = request.form.get('classification', values['classification'])
            try:
                if values['classification'] not in guide_categories(db()):
                    raise ValueError('请选择列表中的文档分类和系列。')
                category, series = guide_location(values['classification'])
                for key in ('title', 'label'):
                    values[key] = values[key].strip()
                    if not 1 <= len(values[key]) <= 120:
                        raise ValueError('文档标题和目录名称需要 1 至 120 个字符。')
                if len(values['content_html'].encode('utf-8')) > 1024 * 1024:
                    raise ValueError('正文太长，请控制在 1 MB 以内。图片和附件请使用上传按钮。')
                content, text, resources = prepare_content(values['content_html'])
                if not text and '<img ' not in content:
                    raise ValueError('请填写文档正文。')
                try:
                    version = int(values['version'])
                except ValueError:
                    raise ValueError('页面版本无效，请刷新后重试。')
                with db():
                    changed = db().execute('UPDATE guides SET title=?,label=?,category=?,series=?,content_html=?,search_text=?,version=version+1,updated_at=CURRENT_TIMESTAMP WHERE slug=? AND version=?', (values['title'], values['label'], category, series, content, text, slug, version))
                    if changed.rowcount != 1:
                        status = 409
                        raise ValueError('资料已在另一个页面更新。本页修改尚未保存，请先复制修改内容，再刷新后重试。')
                    update_asset_references(db(), slug, resources)
                flash('文档已更新，官网已同步显示最新内容。', 'success')
                return redirect(url_for('guides.edit', slug=slug))
            except ValueError as problem:
                error = str(problem)
                status = 409 if status == 409 else 400
        return render_template('guide_edit.html', guide=item, values=values, error=error), status

    @guides.post('/admin/guides/<slug>/upload')
    def upload(slug):
        guide(slug)
        upload = request.files.get('file')
        if not upload or not upload.filename:
            return jsonify(error='请选择一个文件。'), 400
        name = re.sub(r'[\x00-\x1f\x7f]', '', upload.filename.replace('\\', '/').split('/')[-1])[:180]
        suffix = Path(name).suffix.lower()
        images = {'.png': 'PNG', '.jpg': 'JPEG', '.jpeg': 'JPEG', '.gif': 'GIF', '.webp': 'WEBP'}
        if suffix not in images and suffix not in {'.pdf', '.zip', '.stp', '.step', '.json', '.bin', '.hex'}:
            return jsonify(error='支持 PNG、JPG、GIF、WebP 图片，以及 PDF、ZIP、STEP/STP、JSON、BIN、HEX 附件。'), 400
        limit = (10 if suffix in images else 150) * 1024 * 1024
        temporary = None
        stored = None
        try:
            with tempfile.NamedTemporaryFile(dir=files_dir, suffix='.upload', delete=False) as target:
                temporary = Path(target.name)
                size = 0
                while chunk := upload.stream.read(65536):
                    size += len(chunk)
                    if size > limit:
                        raise ValueError('图片不能超过 10 MB，附件不能超过 150 MB。')
                    target.write(chunk)
            if not size:
                raise ValueError('文件为空，请重新选择。')
            media_type = 'application/pdf' if suffix == '.pdf' else 'application/octet-stream'
            width = height = None
            if suffix == '.pdf':
                try:
                    with temporary.open('rb') as source:
                        if source.read(5) != b'%PDF-':
                            raise ValueError('文件内容不是有效的 PDF。')
                        source.seek(0)
                        pdf = PdfReader(source)
                        if pdf.is_encrypted or not len(pdf.pages):
                            raise ValueError('请上传未加密、至少包含一页的 PDF。')
                except PdfReadError:
                    raise ValueError('无法读取这份 PDF，请重新导出后上传。')
            if suffix in images:
                with warnings.catch_warnings():
                    warnings.simplefilter('error', Image.DecompressionBombWarning)
                    with Image.open(temporary) as picture:
                        if picture.format != images[suffix]:
                            raise ValueError('图片内容与文件格式不符，请重新导出后上传。')
                        width, height = picture.size
                        picture.verify()
                media_type = {'PNG': 'image/png', 'JPEG': 'image/jpeg', 'GIF': 'image/gif', 'WEBP': 'image/webp'}[images[suffix]]
            identifier = uuid4().hex
            stored = files_dir / (identifier + suffix)
            temporary.replace(stored)
            temporary = None
            resource = quote(f'/guides/{slug}/assets/{identifier}/{name}', safe='/')
            with db():
                db().execute('INSERT INTO guide_assets (id,guide_slug,public_url,stored_name,original_name,media_type,byte_size) VALUES (?,?,?,?,?,?,?)', (identifier, slug, resource, stored.name, name, media_type, size))
            stored = None
            return jsonify(url=resource, name=name, image=suffix in images, width=width, height=height,
                           view_url='/vendor/pdfjs-6.4.299-legacy/web/viewer.html?file=' + quote(resource, safe='') + '#zoom=page-fit' if suffix == '.pdf' else resource,
                           download_url=resource + '?download=1'), 201
        except (ValueError, SyntaxError, UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning) as problem:
            message = str(problem) if isinstance(problem, ValueError) else '无法读取这张图片或保存文件，请检查文件后重试。'
            return jsonify(error=message), 400
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
            if stored is not None:
                stored.unlink(missing_ok=True)

    @guides.get('/guides/catalog.json')
    def catalog():
        return jsonify([{'slug': item['slug'], 'title': item['title'], 'label': item['label'], 'category': item['category'], 'series': item['series'], 'text': item['search_text']} for item in db().execute('SELECT * FROM guides WHERE published=1 ORDER BY sort_order,slug')])

    @guides.get('/guides/<slug>/content.html')
    def content(slug):
        return app.response_class(guide(slug)['content_html'], mimetype='text/html')

    @guides.get('/guides/<slug>/<path:filename>')
    def asset(slug, filename):
        resource = quote(f'/guides/{slug}/{filename}', safe='/')
        item = db().execute('SELECT * FROM guide_assets WHERE public_url=?', (resource,)).fetchone()
        if not item or (not g.admin and not db().execute('SELECT 1 FROM guide_asset_refs WHERE asset_id=? LIMIT 1', (item['id'],)).fetchone()):
            abort(404)
        inline = item['media_type'].startswith('image/') or item['media_type'] == 'application/pdf'
        return send_file(files_dir / item['stored_name'], mimetype=item['media_type'], download_name=item['original_name'],
                         as_attachment=not inline or request.args.get('download') == '1', conditional=True)

    from feishu_sync import register_sync
    register_sync(app, db, guides)
    app.register_blueprint(guides)
