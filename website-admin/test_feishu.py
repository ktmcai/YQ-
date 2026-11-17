import copy
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from app import create_app
from feishu import FeishuClient, Renderer, SOURCES, SyncError, table_html, document_url, sheet_cell_style, sheet_dimensions
from feishu_sync import sync_document
from guides import prepare_content


def paragraph(identifier, text, kind=2):
    field = 'text' if kind == 2 else 'heading1'
    return {'block_id': identifier, 'block_type': kind, field: {'elements': [{'text_run': {'content': text}}]}}


class FakeFeishu:
    def __init__(self, *args):
        pass

    def document(self, source):
        return {'document_id': 'root', 'title': '飞书新标题', 'revision_id': 2}, [
            {'block_id': 'root', 'block_type': 1, 'children': ['heading', 'text', 'image']},
            paragraph('heading', '参数', 3), paragraph('text', '同步后的 48V 参数'),
            {'block_id': 'image', 'block_type': 27, 'image': {'token': 'picture'}}]

    def resolve(self, url):
        return url.rsplit('/', 1)[-1]

    def metadata(self, identifier):
        return {'document_id': identifier, 'title': '新产品资料', 'revision_id': 2}

    def download(self, token, destination, board=False):
        Image.new('RGB', (8, 8), 'red').save(destination, format='PNG')

    def verify_revision(self, meta):
        pass


class SyncTests(unittest.TestCase):
    def setUp(self):
        self.storage = tempfile.TemporaryDirectory()
        self.data = Path(self.storage.name)
        self.config = {'TESTING': True, 'SECRET_KEY': 'test', 'DATA_DIR': str(self.data),
                       'SESSION_COOKIE_SECURE': False, 'FEISHU_APP_ID': 'test', 'FEISHU_APP_SECRET': 'test-secret'}
        self.app = create_app(self.config)
        self.original = '<h2 id="section-1">参数</h2><p>官网原内容</p>'
        with self.connection() as db:
            db.execute("INSERT INTO guides(slug,title,label,category,sort_order,content_html,search_text) VALUES ('jp57-08','原标题','目录名称','AXIS',1,?,'官网原内容')", (self.original,))
            db.execute("INSERT INTO admin(id,password_hash) VALUES (1,'not-used')")
            db.execute("INSERT INTO guide_sources(slug,url,document_id) VALUES ('jp57-08',?,?)", (SOURCES['jp57-08']['url'], SOURCES['jp57-08']['document_id']))
        self.client = self.app.test_client()
        with self.client.session_transaction() as session:
            session.update(authenticated=True, auth_version=1, csrf='test-csrf')

    def tearDown(self):
        self.doCleanups()
        self.storage.cleanup()

    def connection(self):
        db = sqlite3.connect(self.data / 'documents.sqlite')
        db.row_factory = sqlite3.Row
        self.addCleanup(db.close)
        return db

    def start(self, identifier='job'):
        with self.connection() as db:
            version = db.execute('SELECT version FROM guides').fetchone()[0]
            db.execute("INSERT INTO guide_sync_jobs(id,slug,base_version,status,message) VALUES (?,'jp57-08',?,'running','test')", (identifier, version))

    def run_sync(self, identifier='job'):
        with patch('feishu_sync.FeishuClient', FakeFeishu):
            sync_document(self.app, identifier)

    def state(self):
        with self.connection() as db:
            return dict(db.execute('SELECT * FROM guides').fetchone())

    def test_success_backup_assets_title_and_idempotency(self):
        self.start(); self.run_sync()
        guide = self.state()
        self.assertEqual((guide['title'], guide['label'], guide['version']), ('飞书新标题', '目录名称', 2))
        self.assertIn('section-1', guide['content_html'])
        self.assertIn('48V', guide['search_text'])
        with self.connection() as db:
            self.assertEqual(db.execute('SELECT content_html FROM guide_sync_history').fetchone()[0], self.original)
            resource = db.execute('SELECT public_url FROM guide_assets').fetchone()[0]
        image = self.app.test_client().get(resource)
        self.assertEqual(image.status_code, 200); image.close()
        self.start('again'); self.run_sync('again')
        self.assertEqual(self.state(), guide)
        with self.connection() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM guide_assets').fetchone()[0], 1)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM guide_sync_history').fetchone()[0], 1)
        self.assertEqual(len(list((self.data / 'guide-files').iterdir())), 1)

    def test_remote_change_keeps_old_content_and_no_partial_files(self):
        self.start()
        with patch.object(FakeFeishu, 'verify_revision', side_effect=SyncError('飞书正在修改')):
            self.run_sync()
        self.assertEqual(self.state()['content_html'], self.original)
        with self.connection() as db:
            self.assertEqual(db.execute('SELECT status FROM guide_sync_jobs').fetchone()[0], 'failed')
            self.assertEqual(db.execute('SELECT COUNT(*) FROM guide_assets').fetchone()[0], 0)
        self.assertEqual(list((self.data / 'guide-files').iterdir()), [])

    def test_local_edit_during_sync_is_preserved(self):
        self.start()
        def edit(meta):
            with self.connection() as db:
                db.execute("UPDATE guides SET content_html='<p>人工修改</p>', version=version+1")
        with patch.object(FakeFeishu, 'verify_revision', side_effect=edit):
            self.run_sync()
        self.assertEqual(self.state()['content_html'], '<p>人工修改</p>')
        self.assertEqual(list((self.data / 'guide-files').iterdir()), [])

    def test_invalid_image_does_not_publish(self):
        self.start()
        with patch.object(FakeFeishu, 'download', side_effect=lambda token, path, board: path.write_bytes(b'not an image')):
            self.run_sync()
        self.assertEqual(self.state()['content_html'], self.original)
        self.assertEqual(list((self.data / 'guide-files').iterdir()), [])

    def test_missing_sheet_styles_keeps_published_content(self):
        self.start()
        document = ({'document_id': 'root', 'title': '新标题', 'revision_id': 2}, [
            {'block_id': 'root', 'block_type': 1, 'children': ['sheet']},
            {'block_id': 'sheet', 'block_type': 30, 'sheet': {'token': 'book_sheet'}}])
        with patch.object(FakeFeishu, 'document', return_value=document), patch.object(
                FakeFeishu, 'sheet', create=True, side_effect=SyncError('飞书表格样式读取不完整')):
            self.run_sync()
        self.assertEqual(self.state()['content_html'], self.original)
        with self.connection() as db:
            self.assertEqual(db.execute('SELECT status FROM guide_sync_jobs').fetchone()[0], 'failed')
            self.assertEqual(db.execute('SELECT COUNT(*) FROM guide_sync_history').fetchone()[0], 0)

    def test_route_auth_csrf_stale_version_and_single_job(self):
        path = '/admin/guides/jp57-08/sync'
        self.assertEqual(self.app.test_client().get('/admin/guides/sync-status').status_code, 302)
        self.assertEqual(self.app.test_client().post(path).status_code, 302)
        self.assertEqual(self.client.post(path).status_code, 400)
        self.assertEqual(self.client.post(path, data={'csrf_token': 'test-csrf', 'version': 0}).status_code, 409)
        with patch('feishu_sync.threading.Thread') as thread:
            self.assertEqual(self.client.post(path, data={'csrf_token': 'test-csrf', 'version': 1}).status_code, 202)
            thread.return_value.start.assert_called_once()
            self.assertEqual(self.client.post(path, data={'csrf_token': 'test-csrf', 'version': 1}).status_code, 409)
        status = self.client.get('/admin/guides/sync-status')
        self.assertNotIn('test-secret', status.get_data(as_text=True))
        self.assertEqual(status.json['jobs'][0]['status'], 'running')

    def test_restart_releases_interrupted_job(self):
        self.start()
        create_app(self.config)
        self.assertEqual(self.client.get('/admin/guides/sync-status').json['jobs'][0]['status'], 'failed')

    def test_transaction_failure_rolls_back_database_and_moved_files(self):
        self.start()
        with patch('guides.update_asset_references', side_effect=sqlite3.OperationalError('simulated failure')):
            self.run_sync()
        self.assertEqual(self.state()['content_html'], self.original)
        self.assertEqual(list((self.data / 'guide-files').iterdir()), [])
        with self.connection() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM guide_sync_history').fetchone()[0], 0)

    def import_new(self, url='https://example.feishu.cn/docx/NewDocument', **fields):
        with patch('feishu_sync.FeishuClient', FakeFeishu), patch('feishu_sync.threading.Thread'):
            return self.client.post('/admin/guides/import', data={'csrf_token': 'test-csrf', 'url': url, **fields})

    def test_import_is_hidden_until_complete_and_remains_bound_after_restart(self):
        response = self.import_new(category='YONIQ AXIS')
        self.assertEqual(response.status_code, 202)
        identifier = response.json['id']
        with self.connection() as db:
            slug = db.execute('SELECT slug FROM guide_sync_jobs WHERE id=?', (identifier,)).fetchone()[0]
            guide = dict(db.execute('SELECT * FROM guides WHERE slug=?', (slug,)).fetchone())
        visitor = self.app.test_client()
        self.assertEqual(guide['published'], 0)
        self.assertNotIn(slug, [row['slug'] for row in visitor.get('/guides/catalog.json').json])
        self.assertEqual(visitor.get('/guides/' + slug + '/content.html').status_code, 404)
        self.assertEqual(self.client.get('/admin/guides/' + slug + '/edit').status_code, 404)
        self.run_sync(identifier)
        self.assertIn(slug, [row['slug'] for row in visitor.get('/guides/catalog.json').json])
        self.assertIn('48V', visitor.get('/guides/' + slug + '/content.html').get_data(as_text=True))
        with self.connection() as db:
            self.assertEqual(db.execute('SELECT category,version FROM guides WHERE slug=?', (slug,)).fetchone()[:], ('YONIQ AXIS', 1))
            self.assertEqual(db.execute('SELECT COUNT(*) FROM guide_sync_history').fetchone()[0], 0)
        create_app(self.config)
        self.assertIn('NewDocument', self.client.get('/admin/guides').get_data(as_text=True))
        with patch('feishu_sync.threading.Thread'):
            again = self.client.post('/admin/guides/' + slug + '/sync', data={'csrf_token': 'test-csrf', 'version': 1})
        self.assertEqual(again.status_code, 202)
        self.run_sync(again.json['id'])
        with self.connection() as db:
            self.assertEqual(db.execute('SELECT version FROM guides WHERE slug=?', (slug,)).fetchone()[0], 1)

    def test_failed_import_is_private_and_can_retry(self):
        response = self.import_new()
        identifier = response.json['id']
        with patch.object(FakeFeishu, 'verify_revision', side_effect=SyncError('内容有变化')):
            self.run_sync(identifier)
        with self.connection() as db:
            slug = db.execute('SELECT slug FROM guide_sync_jobs WHERE id=?', (identifier,)).fetchone()[0]
            self.assertEqual(db.execute('SELECT published FROM guides WHERE slug=?', (slug,)).fetchone()[0], 0)
        self.assertEqual(len(self.client.get('/guides/catalog.json').json), 1)
        self.assertEqual(list((self.data / 'guide-files').iterdir()), [])
        with patch('feishu_sync.threading.Thread'):
            retry = self.client.post('/admin/guides/' + slug + '/sync', data={'csrf_token': 'test-csrf', 'version': 0})
        self.assertEqual(retry.status_code, 202)
        self.run_sync(retry.json['id'])
        self.assertEqual(len(self.client.get('/guides/catalog.json').json), 2)

    def test_import_and_repeat_sync_fill_blank_protocol_sections(self):
        blocks = [paragraph('protocols', '3. 协议手册', 3),
                  {'block_id': 'canopen', 'block_type': 4, 'heading2': {'elements': [{'text_run': {'content': 'CANOPEN协议'}}]}},
                  paragraph('space', '\n\u00a0'),
                  {'block_id': 'serial', 'block_type': 4, 'heading2': {'elements': [{'text_run': {'content': '串口协议'}}]}},
                  paragraph('next', '4. 快速上手', 3)]
        root = {'block_id': 'root', 'block_type': 1, 'children': [b['block_id'] for b in blocks]}
        document = ({'document_id': 'root', 'title': '新设备资料', 'revision_id': 2}, [root] + blocks)
        response = self.import_new(category='YONIQ AXIS / JP')
        self.assertEqual(response.status_code, 202)
        with patch.object(FakeFeishu, 'document', return_value=document):
            self.run_sync(response.json['id'])
            item = next(row for row in self.client.get('/guides/catalog.json').json if row['slug'] != 'jp57-08')
            path = '/guides/' + item['slug'] + '/content.html'
            content = self.client.get(path).get_data(as_text=True)
            for target in ('canopen-ethercat', 'serial-protocol'):
                self.assertEqual(content.count('href="/guides.html?doc=' + target + '"'), 1)
            self.assertIn('section-canopen', content)
            self.assertIn('section-serial', content)
            self.assertIn('CANopen / EtherCAT 用户手册', item['text'])
            self.assertIn('串口协议手册', item['text'])
            with patch('feishu_sync.threading.Thread'):
                again = self.client.post('/admin/guides/' + item['slug'] + '/sync', data={'csrf_token': 'test-csrf', 'version': 1})
            self.assertEqual(again.status_code, 202)
            self.run_sync(again.json['id'])
            self.assertEqual(self.client.get(path).get_data(as_text=True), content)
        with self.connection() as db:
            self.assertEqual(db.execute('SELECT version FROM guides WHERE slug=?', (item['slug'],)).fetchone()[0], 1)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM guide_assets').fetchone()[0], 0)

    def test_imported_axis_series_survives_sync(self):
        response = self.import_new(category='YONIQ AXIS / JS')
        self.assertEqual(response.status_code, 202)
        self.run_sync(response.json['id'])
        item = next(row for row in self.client.get('/guides/catalog.json').json if row['slug'] != 'jp57-08')
        self.assertEqual((item['category'], item['series']), ('YONIQ AXIS', 'JS'))
        with patch('feishu_sync.threading.Thread'):
            again = self.client.post('/admin/guides/' + item['slug'] + '/sync', data={'csrf_token': 'test-csrf', 'version': 1})
        self.run_sync(again.json['id'])
        item = next(row for row in self.client.get('/guides/catalog.json').json if row['slug'] != 'jp57-08')
        self.assertEqual(item['series'], 'JS')

    def test_duplicate_link_query_and_wiki_alias_do_not_create_another_guide(self):
        existing = SOURCES['jp57-08']
        response = self.import_new(existing['url'] + '?from=copy#section')
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json['existing_url'], '/admin/guides#guide-jp57-08')
        with patch.object(FakeFeishu, 'resolve', return_value=existing['document_id']):
            self.assertEqual(self.import_new('https://example.feishu.cn/wiki/Alias').status_code, 409)
        with self.connection() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM guides').fetchone()[0], 1)

    def test_import_denied_permission_invalid_category_and_auth(self):
        with patch.object(FakeFeishu, 'metadata', side_effect=SyncError('请添加文档应用')):
            response = self.import_new()
        self.assertEqual(response.status_code, 400)
        self.assertIn('添加文档应用', response.json['error'])
        self.assertEqual(self.import_new(category='unknown').status_code, 400)
        self.assertEqual(self.client.post('/admin/guides/import').status_code, 400)
        self.assertEqual(self.app.test_client().post('/admin/guides/import').status_code, 302)
        with self.connection() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM guides').fetchone()[0], 1)

    def test_import_and_sync_share_the_single_job_lock(self):
        self.start()
        self.assertEqual(self.import_new().status_code, 409)
        self.run_sync()
        self.assertEqual(self.import_new().status_code, 202)
        response = self.client.post('/admin/guides/jp57-08/sync', data={'csrf_token': 'test-csrf', 'version': 2})
        self.assertEqual(response.status_code, 409)


class ConversionTests(unittest.TestCase):
    def test_protocol_placeholder_heading_variants_and_idempotency(self):
        from feishu import fill_protocol_placeholders
        for title in ('CANOPEN协议', 'CANopen 协议', 'EtherCAT协议', 'CANopen / EtherCAT 协议', 'CANopen／EtherCAT协议'):
            with self.subTest(title=title):
                content = ('<h2 id="section-manual">3. 协议手册</h2><h3 id="section-can"><strong>' + title +
                           '</strong></h3><p><span> &nbsp;<br></span></p><h3 id="section-serial">串口协议</h3>')
                filled = fill_protocol_placeholders(content)
                self.assertEqual(filled.count('doc=canopen-ethercat'), 1)
                self.assertEqual(filled.count('doc=serial-protocol'), 1)
                self.assertIn('id="section-can"', filled)
                self.assertEqual(fill_protocol_placeholders(filled), filled)

    def test_protocol_placeholder_preserves_content_and_respects_section_scope(self):
        from feishu import fill_protocol_placeholders
        for body in ('<p>请联系支持</p>', '<p><a href="/guides.html?doc=serial-protocol">串口协议手册</a></p>',
                     '<img src="/guides/a/pic.png">', '<table><tr><td></td></tr></table>',
                     '<h4>配置说明</h4><p>内容</p>', '<a href="/guides/a/manual.pdf">下载 PDF</a>'):
            with self.subTest(body=body):
                content = '<h2>协议手册</h2><h3>串口协议</h3>' + body + '<h2>快速上手</h2>'
                self.assertEqual(fill_protocol_placeholders(content), content)
        for content in ('<h2>通信说明</h2><h3>串口协议</h3>',
                        '<h2>协议手册</h2><h3>其他协议</h3>',
                        '<h2>协议手册</h2><h2>快速上手</h2><h3>串口协议</h3>'):
            self.assertEqual(fill_protocol_placeholders(content), content)

    def test_protocol_manual_itself_does_not_get_placeholder_links(self):
        blocks = [paragraph('protocols', '协议手册', 3),
                  {'block_id': 'serial', 'block_type': 4, 'heading2': {'elements': [{'text_run': {'content': '串口协议'}}]}}]
        root = {'block_id': 'root', 'block_type': 1, 'children': ['protocols', 'serial']}
        for slug in ('serial-protocol', 'canopen-ethercat'):
            content = Renderer(None, {'document_id': 'root'}, [root] + blocks, None, '', slug).render()
            self.assertNotIn('/guides.html?doc=', content)

    def test_only_supported_feishu_urls_are_accepted(self):
        self.assertEqual(document_url(' https://example.feishu.cn/wiki/Token/?from=copy#section '), 'https://example.feishu.cn/wiki/Token')
        for url in ['http://example.feishu.cn/docx/T', 'https://feishu.cn.evil.com/docx/T', 'https://example.feishu.cn:444/docx/T',
                    'https://user@example.feishu.cn/docx/T', 'https://example.feishu.cn/sheets/T', 'https://127.0.0.1/docx/T',
                    'https://example.feishu.cn/docx/../../auth', 'https://example.feishu.cn/docx/T\nMore', 'https://example.feishu.cn\\@evil.com/docx/T', '']:
            with self.subTest(url=url), self.assertRaises(SyncError): document_url(url)

    def test_new_imported_document_links_are_internal(self):
        source = {'new-product': {'url': 'https://example.feishu.cn/wiki/Wiki', 'document_id': 'Doc', 'published': 1}}
        renderer = Renderer(None, {}, [], None, '', 'another', source)
        self.assertEqual(renderer.link('https://example.feishu.cn/docx/Doc'), '/guides.html?doc=new-product')
        source['new-product']['published'] = 0
        self.assertEqual(renderer.link('https://example.feishu.cn/wiki/Wiki'), 'https://example.feishu.cn/wiki/Wiki')

    def render(self, blocks, client=None):
        root = {'block_id': 'root', 'block_type': 1, 'children': [b['block_id'] for b in blocks]}
        return Renderer(client, {'document_id': 'root'}, [root] + blocks,
                        lambda *args: ('/guides/jp57-08/assets/file.json', None, None), '', 'jp57-08').render()

    def test_inline_file_is_rendered_once_even_when_listed_as_child(self):
        block = {'block_id': 'text', 'block_type': 2, 'children': ['file'],
                 'text': {'elements': [{'inline_block': {'block_id': 'file'}}]}}
        class Client:
            def inline(self, doc, identifier):
                return {'block_id': 'file', 'block_type': 23, 'file': {'token': 'file', 'name': 'firmware.json'}}
        self.assertEqual(self.render([block], Client()).count('>firmware.json</a>'), 1)

    def test_shared_protocol_manual_links_do_not_download_device_copies(self):
        from feishu import CANOPEN_MANUAL_FILES
        from unittest.mock import Mock
        for name in CANOPEN_MANUAL_FILES:
            with self.subTest(name=name):
                blocks = [{'block_id': 'root', 'block_type': 1, 'children': ['manual']},
                          {'block_id': 'manual', 'block_type': 23, 'file': {'token': 'pdf', 'name': name}}]
                asset = Mock(side_effect=AssertionError('Protocol copy must not be downloaded'))
                renderer = Renderer(None, {'document_id': 'root'}, blocks, asset, '', 'jp57-08')
                content, text, references = prepare_content(renderer.render())
                self.assertIn('href="/guides.html?doc=canopen-ethercat"', content)
                self.assertEqual(text, 'CANopen / EtherCAT 用户手册')
                self.assertEqual(references, set())
                self.assertEqual(renderer.stats['files'], 0)
                asset.assert_not_called()

    def test_other_pdfs_and_protocol_page_download_are_preserved(self):
        for slug, name in [('serial-protocol', '串口协议手册.pdf'),
                           ('jp57-08', 'other_CANopen.pdf'),
                           ('canopen-ethercat', 'YONIQ_AXIS_CANopen_EtherCAT用户手册.pdf')]:
            with self.subTest(slug=slug, name=name):
                blocks = [{'block_id': 'root', 'block_type': 1, 'children': ['manual']},
                          {'block_id': 'manual', 'block_type': 23, 'file': {'token': 'pdf', 'name': name}}]
                renderer = Renderer(None, {'document_id': 'root'}, blocks,
                                    lambda *args: ('/guides/test/manual.pdf', None, None), '', slug)
                content = renderer.render()
                self.assertIn('/vendor/pdfjs-', content)
                self.assertIn('下载 PDF', content)
                self.assertEqual(renderer.stats['files'], 1)

    def test_serial_pdf_uses_online_manual_without_duplicate_source_link(self):
        from unittest.mock import Mock
        manual = {'block_id': 'pdf', 'block_type': 23, 'file': {'token': 'pdf', 'name': '串口协议手册.pdf'}}
        for existing in ('none', 'text_run', 'mention_doc'):
            for pdf_first in (True, False):
                with self.subTest(existing=existing, pdf_first=pdf_first):
                    blocks = [manual]
                    if existing != 'none':
                        url = SOURCES['serial-protocol']['url']
                        element = ({'text_run': {'content': '串口协议手册', 'text_element_style': {'link': {'url': url}}}}
                                   if existing == 'text_run' else {'mention_doc': {'url': url, 'title': '串口协议手册'}})
                        entry = {'block_id': 'online', 'block_type': 2, 'text': {'elements': [element]}}
                        blocks.insert(1 if pdf_first else 0, entry)
                    root = {'block_id': 'root', 'block_type': 1, 'children': [b['block_id'] for b in blocks]}
                    asset = Mock(side_effect=AssertionError('Serial PDF must not be downloaded'))
                    renderer = Renderer(None, {'document_id': 'root'}, [root] + blocks, asset, '', 'jp57-08')
                    content, text, references = prepare_content(renderer.render())
                    self.assertEqual(content.count('href="/guides.html?doc=serial-protocol"'), 1)
                    self.assertEqual(text, '串口协议手册')
                    self.assertEqual(references, set())
                    self.assertEqual(renderer.stats['files'], 0)
                    asset.assert_not_called()

    def test_unknown_missing_and_orphan_blocks_fail(self):
        with self.assertRaises(SyncError): self.render([{'block_id': 'unknown', 'block_type': 999}])
        with self.assertRaises(SyncError): self.render([{'block_id': 'wrapper', 'block_type': 24, 'children': ['missing']}])
        with self.assertRaises(SyncError):
            Renderer(None, {'document_id': 'root'}, [{'block_id': 'root', 'block_type': 1}, paragraph('orphan', 'lost')], None, '', '').render()

    def test_text_and_code_are_escaped(self):
        content = self.render([paragraph('text', '<script>alert(1)</script>')])
        self.assertIn('&lt;script&gt;', content)
        self.assertNotIn('<script>', content)

    def test_merge_layout_and_invalid_ranges(self):
        content = table_html(2, 2, [['A', 'B'], ['', 'C']], [(0, 0, 2, 1)])
        self.assertIn('rowspan="2"', content)
        self.assertEqual(content.count('<td'), 3)
        with self.assertRaises(SyncError): table_html(2, 2, [], [(0, 0, 3, 1)])

    def test_sheet_colors_survive_conversion_merges_and_sanitizing(self):
        class Client:
            def sheet(self, token):
                return {'rowCount': 2, 'columnCount': 2,
                        'column_widths': [105, 578], 'row_heights': [27, 48],
                        'merges': [{'startRowIndex': 0, 'startColumnIndex': 0, 'rowCount': 2, 'columnCount': 1}],
                        'cell_styles': {(0, 0): sheet_cell_style({'background_color': 'rgb(225, 234, 255)',
                                                                 'font_family': '宋体', 'font_size': 11,
                                                                 'font_weight': 'bold', 'horizontal_alignment': 'center',
                                                                 'vertical_alignment': 'middle'}),
                                        (1, 1): sheet_cell_style({'background_color': '#d9f3fd', 'font_color': '#d83931'})}}, [
                    ['电机参数', '48V'], ['', '30NM']]
        content = self.render([{'block_id': 'sheet', 'block_type': 30, 'sheet': {'token': 'workbook_sheet'}}], Client())
        cleaned, text, _ = prepare_content(content)
        self.assertIn('rowspan="2"', cleaned)
        self.assertEqual(cleaned.count('<td'), 3)
        self.assertIn('background-color:rgb(225, 234, 255)', cleaned)
        self.assertIn('font-weight:bold', cleaned)
        self.assertIn('text-align:center', cleaned)
        self.assertIn('vertical-align:middle', cleaned)
        self.assertIn('color:#d83931', cleaned)
        self.assertIn('background-color:#d9f3fd', cleaned)
        self.assertIn('font-family:SimSun', cleaned)
        self.assertIn('font-size:14px', cleaned)
        self.assertIn('class="feishu-document"', cleaned)
        self.assertIn('class="feishu-table feishu-sheet"', cleaned)
        self.assertIn('<col style="width:105px">', cleaned)
        self.assertIn('<col style="width:578px">', cleaned)
        self.assertIn('<tr style="height:48px">', cleaned)
        self.assertEqual(text, '电机参数 48V 30NM')

    def test_sheet_style_values_cannot_inject_css_or_markup(self):
        style = sheet_cell_style({'font_color': 'red;position:fixed', 'background_color': 'url(https://example.org/x)',
                                  'font_family': 'Arial";position:fixed', 'font_size': '12px;display:none',
                                  'font_weight': 'bold" onclick="x', 'horizontal_alignment': 'left;display:none'})
        self.assertEqual(style, '')
        self.assertEqual(sheet_cell_style({'font_color': 'rgb(999, 0, 0)'}), '')
        self.assertEqual(sheet_cell_style({'background_color': 'rgba(255, 255, 255, 0.5)'}),
                         'background-color:rgba(255, 255, 255, 0.5)')
        self.assertEqual(sheet_cell_style({'font_color': '#12abef', 'font_style': 'italic', 'font_line': 'underline'}),
                         'color:#12abef;font-style:italic;text-decoration:underline')

    def test_font_sizes_match_sheet_canvas_and_safe_font_names(self):
        self.assertEqual(sheet_cell_style({'font_family': 'Arial Black', 'font_size': 12}),
                         'font-family:"Arial Black",sans-serif;font-size:16px')
        for size in (0, -1, True, float('nan'), float('inf'), 301):
            with self.subTest(size=size):
                self.assertEqual(sheet_cell_style({'font_size': size}), '')

    def test_sheet_dimension_groups_expand_and_require_complete_coverage(self):
        self.assertEqual(sheet_dimensions([{'cols': 'A:Z', 'width': 105}, {'cols': 'AA:AB', 'width': 33}],
                                          'cols', 'width', 28), [105] * 26 + [33, 33])
        self.assertEqual(sheet_dimensions([{'rows': '1:2', 'height': 27}, {'rows': '3:3', 'height': 48}],
                                          'rows', 'height', 3), [27, 27, 48])
        for groups in ([], [{'cols': 'A:A', 'width': 10}], [{'cols': 'B:A', 'width': 10}],
                       [{'cols': 'A:C', 'width': 10}], [{'cols': 'A:B', 'width': -1}],
                       [{'cols': 'A:B', 'width': 10}, {'cols': 'B:B', 'width': 20}]):
            with self.subTest(groups=groups), self.assertRaises(SyncError):
                sheet_dimensions(groups, 'cols', 'width', 2)

    def test_sheet_layout_revision_change_is_rejected(self):
        client = FeishuClient.__new__(FeishuClient); client.sheet_revisions = {}
        client.sheet_styles = lambda *args: {}
        def read(path, payload=None):
            if path.endswith('/metainfo'):
                return {'sheets': [{'sheetId': 'sheet', 'rowCount': 1, 'columnCount': 1}], 'properties': {'revision': 8}}
            if '/values/' in path:
                return {'revision': 8, 'valueRange': {'values': [['value']]}}
            return {'output': json.dumps({'revision': 9})}
        client.json = read
        with self.assertRaises(SyncError): client.sheet('book_sheet')

    def test_native_table_widths_and_grid_columns_survive_sanitizing(self):
        blocks = [
            {'block_id': 'root', 'block_type': 1, 'children': ['grid', 'table']},
            {'block_id': 'grid', 'block_type': 24, 'children': ['column']},
            {'block_id': 'column', 'block_type': 25, 'grid_column': {'width_ratio': 50}, 'children': ['text']},
            paragraph('text', '分栏正文'),
            {'block_id': 'table', 'block_type': 31, 'table': {'property': {'row_size': 1, 'column_size': 1,
              'column_width': [256]}, 'cells': ['cell']}},
            {'block_id': 'cell', 'block_type': 32, 'children': ['cell-text']}, paragraph('cell-text', '原表格')]
        content = Renderer(None, {'document_id': 'root'}, blocks, None, '', 'test').render()
        cleaned, text, _ = prepare_content(content)
        self.assertIn('class="feishu-columns"', cleaned)
        self.assertIn('class="feishu-column" style="width:50%"', cleaned)
        self.assertIn('<col style="width:256px">', cleaned)
        self.assertEqual(text, '分栏正文 原表格')
        with self.assertRaises(SyncError): self.render([paragraph('empty', '')])

    def test_empty_columns_cannot_publish_an_empty_document(self):
        blocks = [
            {'block_id': 'root', 'block_type': 1, 'children': ['grid']},
            {'block_id': 'grid', 'block_type': 24, 'children': ['column']},
            {'block_id': 'column', 'block_type': 25, 'grid_column': {'width_ratio': 100}, 'children': ['empty']},
            paragraph('empty', '')]
        with self.assertRaises(SyncError):
            Renderer(None, {'document_id': 'root'}, blocks, None, '', 'test').render()

    def test_document_text_colors_preserve_bold_links_and_background(self):
        block = paragraph('text', '<注意>')
        block['text']['elements'][0]['text_run']['text_element_style'] = {
            'bold': True, 'text_color': 1, 'background_color': 15, 'link': {'url': 'https://example.org/'}}
        content, text, _ = prepare_content(self.render([block]))
        self.assertIn('color:#d83931;background-color:#f2f3f5', content)
        self.assertIn('<strong>&lt;注意&gt;</strong>', content)
        self.assertIn('href="https://example.org/"', content)
        self.assertEqual(text, '<注意>')

    def style_client(self, result):
        client = FeishuClient.__new__(FeishuClient)
        client.json = lambda path, payload: {'output': json.dumps(result)}
        return client

    def style_response(self):
        return {'has_more': False, 'ranges': [{'actual_range': 'A1:B2', 'row_indices': [1, 2], 'col_indices': ['A', 'B'],
                'cells': [[{'cell_styles': {'background_color': '#e1eaff'}}, {'cell_styles': {}}],
                          [{'cell_styles': {}}, {'cell_styles': {'font_color': 'rgb(216, 57, 49)'}}]]}]}

    def test_sheet_style_coordinates_include_empty_and_merged_cells(self):
        styles = self.style_client(self.style_response()).sheet_styles('book', 'sheet', 2, 2)
        self.assertEqual(len(styles), 4)
        self.assertEqual(styles[0, 0], 'background-color:#e1eaff')
        self.assertEqual(styles[1, 1], 'color:rgb(216, 57, 49)')

    def test_partial_or_misaligned_sheet_styles_fail_before_publication(self):
        for change in ('more', 'range', 'rows', 'columns', 'short', 'missing_style', 'truncated'):
            response = copy.deepcopy(self.style_response()); region = response['ranges'][0]
            if change == 'more': response['has_more'] = True
            if change == 'range': region['actual_range'] = 'A1:B1'
            if change == 'rows': region['row_indices'] = [2, 3]
            if change == 'columns': region['col_indices'] = ['B', 'C']
            if change == 'short': region['cells'][1].pop()
            if change == 'missing_style': region['cells'][0][0] = {}
            if change == 'truncated': region['truncated'] = True
            with self.subTest(change=change), self.assertRaises(SyncError):
                self.style_client(response).sheet_styles('book', 'sheet', 2, 2)

    def test_sheet_styles_read_bounded_ranges_with_conditional_colors(self):
        client = FeishuClient.__new__(FeishuClient); calls = []
        def read(path, payload):
            args = json.loads(payload['input']); calls.append(args)
            self.assertTrue(path.endswith('/tools/invoke_read'))
            self.assertEqual(payload['tool_name'], 'get_cell_ranges')
            self.assertTrue(args['include_styles']); self.assertTrue(args['include_conditional_format_style'])
            rows = list(range(1, 101)) if len(calls) == 1 else [101]
            return {'output': json.dumps({'has_more': False, 'ranges': [{
                'actual_range': args['ranges'][0], 'row_indices': rows, 'col_indices': ['A'],
                'cells': [[{'cell_styles': {'background_color': '#d9f3fd'}}] for _ in rows]}]})}
        client.json = read
        styles = client.sheet_styles('book', 'sheet', 101, 1)
        self.assertEqual([c['ranges'] for c in calls], [['A1:A100'], ['A101:A101']])
        self.assertEqual(styles[100, 0], 'background-color:#d9f3fd')

    def test_pagination_reads_latest_and_detects_repeated_cursor(self):
        client = FeishuClient.__new__(FeishuClient)
        client.metadata = lambda identifier: {'document_id': identifier, 'revision_id': 2}
        calls = []
        def page(path):
            calls.append(path)
            return {'items': [paragraph(str(len(calls)), 'page')], 'has_more': len(calls) == 1, 'page_token': 'next'}
        client.json = page
        _, blocks = client.document({'url': 'https://example.feishu.cn/docx/doc', 'document_id': 'doc'})
        self.assertEqual(len(blocks), 2)
        self.assertIn('page_token=next', calls[1])
        self.assertNotIn('document_revision_id', calls[0])
        client.json = lambda path: {'items': [], 'has_more': True, 'page_token': 'same'}
        with self.assertRaises(SyncError): client.document({'url': 'https://example.feishu.cn/docx/doc', 'document_id': 'doc'})

    def test_revision_change_rejected(self):
        client = FeishuClient.__new__(FeishuClient)
        client.metadata = lambda identifier: {'revision_id': 3}
        with self.assertRaises(SyncError): client.verify_revision({'document_id': 'doc', 'revision_id': 2})


if __name__ == '__main__':
    unittest.main()
