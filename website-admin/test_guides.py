import base64
import io
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from PIL import Image
from pypdf import PdfWriter
from werkzeug.security import generate_password_hash

from app import create_app
from guides import prepare_content
from import_guides import import_guides


class GuideTests(unittest.TestCase):
    def setUp(self):
        self.storage = tempfile.TemporaryDirectory()
        self.source = tempfile.TemporaryDirectory()
        self.config = {'TESTING': True, 'SECRET_KEY': 'test-only', 'DATA_DIR': self.storage.name, 'SESSION_COOKIE_SECURE': False}
        self.app = create_app(self.config)
        source = Path(self.source.name)
        (source / 'example').mkdir()
        (source / 'catalog.json').write_text(json.dumps([{'slug': 'example', 'title': '参数手册', 'label': '参数', 'category': '测试'}]), encoding='utf-8')
        (source / 'example' / 'content.html').write_text('<h2 id="section-1">参数</h2><p>原内容</p><table><tbody><tr><th rowspan="2">电机</th><td>48V</td></tr><tr><td>8A</td></tr></tbody></table>', encoding='utf-8')
        import_guides(source, self.storage.name)
        self.client, self.visitor = self.app.test_client(), self.app.test_client()
        with sqlite3.connect(Path(self.storage.name) / 'documents.sqlite') as db:
            db.execute('INSERT INTO admin (id,password_hash) VALUES (1,?)', (generate_password_hash('test-password-123'),))
        db.close()
        self.client.get('/admin/login')
        with self.client.session_transaction() as session:
            self.csrf = session['csrf']
        self.client.post('/admin/login', data={'username': 'admin', 'password': 'test-password-123', 'csrf_token': self.csrf})
        self.client.get('/admin/guides')
        with self.client.session_transaction() as session:
            self.csrf = session['csrf']

    def tearDown(self):
        self.storage.cleanup()
        self.source.cleanup()

    def save(self, content, version=1, **fields):
        return self.client.post('/admin/guides/example/edit', data={'csrf_token': self.csrf, 'title': '新标题', 'label': '新目录', 'version': version, 'content_html': content, **fields})

    def upload(self, name, content):
        return self.client.post('/admin/guides/example/upload', data={'csrf_token': self.csrf, 'file': (io.BytesIO(content), name)}, content_type='multipart/form-data')

    def test_permissions_csrf_and_missing_documents(self):
        self.assertEqual(self.client.get('/admin/guides/').status_code, 200)
        self.assertEqual(self.client.get('/admin/guides').status_code, 200)
        self.assertEqual(self.visitor.get('/admin/guides').status_code, 302)
        self.assertEqual(self.visitor.post('/admin/guides/example/upload').status_code, 302)
        self.assertEqual(self.client.post('/admin/guides/example/edit').status_code, 400)
        self.assertEqual(self.client.post('/admin/guides/example/upload').status_code, 400)
        self.assertEqual(self.visitor.get('/guides/missing/content.html').status_code, 404)

    def test_save_updates_public_content_search_and_survives_restart_import(self):
        content = '<h2 id="section-1">规格</h2><p>新参数921600</p><table><tr><th rowspan="2">电机</th><td>48V</td></tr><tr><td>8A</td></tr></table>'
        self.assertEqual(self.save(content).status_code, 302)
        public = self.visitor.get('/guides/example/content.html').get_data(as_text=True)
        self.assertIn('新参数921600', public)
        self.assertIn('rowspan="2"', public)
        self.assertIn('id="section-1"', public)
        catalog = self.visitor.get('/guides/catalog.json').json[0]
        self.assertEqual(catalog['title'], '新标题')
        self.assertEqual(catalog['label'], '新目录')
        self.assertIn('新参数921600', catalog['text'])
        self.assertEqual(import_guides(self.source.name, self.storage.name), 0)
        restarted = create_app(self.config).test_client()
        self.assertEqual(restarted.get('/guides/example/content.html').get_data(as_text=True), public)

    def test_stale_editor_does_not_overwrite_other_save(self):
        self.assertEqual(self.save('<p>第一个页面的新内容</p>').status_code, 302)
        stale = self.save('<p>第二个页面的修改</p>')
        self.assertEqual(stale.status_code, 409)
        self.assertIn('第二个页面的修改', stale.get_data(as_text=True))
        self.assertIn('第一个页面的新内容', self.visitor.get('/guides/example/content.html').get_data(as_text=True))

    def test_guide_series_reclassification_and_validation(self):
        self.assertEqual(self.save('<p>分类验证</p>', classification='YONIQ AXIS / JC').status_code, 302)
        item = self.visitor.get('/guides/catalog.json').json[0]
        self.assertEqual((item['category'], item['series']), ('YONIQ AXIS', 'JC'))
        axis = self.visitor.get('/api/products').json[0]
        self.assertEqual(next(branch for branch in axis['series'] if branch['code'] == 'JC')['guide_href'], '/guides.html?doc=example')
        self.assertEqual(item['slug'], 'example')
        self.assertEqual(self.save('<p>不应保存</p>', version=2, classification='YONIQ AXIS / INVALID').status_code, 400)
        self.assertEqual(self.save('<p>新分类</p>', version=2, classification='YONIQ DRIVE').status_code, 302)
        item = self.visitor.get('/guides/catalog.json').json[0]
        self.assertEqual((item['category'], item['series']), ('YONIQ DRIVE', ''))

    def test_script_css_and_url_sanitization(self):
        content = '<script>alert(1)</script><svg onload="alert(1)"></svg><p id="document-title" onclick="bad()" style="position:fixed;background-image:url(https://bad.invalid);text-align:center">安全正文</p><a href="javascript:alert(1)">链接</a><a href="https://example.com" target="_blank">外链</a><img src="data:image/svg+xml,bad" onerror="bad()"><iframe src="https://bad.invalid"></iframe>'
        self.assertEqual(self.save(content).status_code, 302)
        public = self.visitor.get('/guides/example/content.html').get_data(as_text=True)
        for bad in ('<script', '<svg', '<iframe', 'onclick', 'onerror', 'javascript:', 'data:image', 'position:', 'background-image', 'id="document-title"'):
            self.assertNotIn(bad, public)
        self.assertIn('text-align:center', public)
        self.assertIn('noopener noreferrer', public)
        self.assertIn('href="https://example.com"', public)

    def test_new_and_duplicate_headings_have_unique_ids(self):
        content, text, _ = prepare_content('<h2 id="section-1">甲</h2><h2 id="section-1">乙</h2><h3>丙</h3><a href="#section-1">原链接</a>')
        import re
        identifiers = re.findall(r'id="([^"]+)"', content)
        self.assertEqual(len(set(identifiers)), 3)
        self.assertIn('href="#section-1"', content)

    def test_upload_preview_publish_download_range_and_filename(self):
        image = io.BytesIO()
        Image.new('RGB', (10, 10)).save(image, format='PNG')
        response = self.upload('../../图片.png', image.getvalue())
        self.assertEqual(response.status_code, 201)
        item = response.json
        self.assertEqual(item['name'], '图片.png')
        self.assertNotIn('..', item['url'])
        self.assertEqual(self.visitor.get(item['url']).status_code, 404)
        preview = self.client.get(item['url'])
        self.assertEqual(preview.mimetype, 'image/png')
        preview.close()
        self.assertEqual(self.save(f'<p>图片说明</p><img src="{item["url"]}" alt="图">').status_code, 302)
        downloaded = self.visitor.get(item['url'])
        self.assertEqual(downloaded.data, image.getvalue())
        downloaded.close()
        partial = self.visitor.get(item['url'], headers={'Range': 'bytes=0-3'})
        self.assertEqual(partial.status_code, 206)
        partial.close()
        self.assertEqual(self.save('<p>移除图片</p>', version=2).status_code, 302)
        self.assertEqual(self.visitor.get(item['url']).status_code, 404)

    def test_pdf_viewer_reference_publishes_attachment(self):
        stream = io.BytesIO()
        writer = PdfWriter()
        writer.add_blank_page(width=300, height=400)
        writer.write(stream)
        item = self.upload('手册.pdf', stream.getvalue()).json
        self.assertEqual(self.save(f'<p><a href="{item["view_url"]}">手册</a></p>').status_code, 302)
        view = self.visitor.get(item['url'])
        self.assertEqual(view.mimetype, 'application/pdf')
        self.assertTrue(view.headers['Content-Disposition'].startswith('inline'))
        view.close()
        download = self.visitor.get(item['download_url'])
        self.assertTrue(download.headers['Content-Disposition'].startswith('attachment'))
        download.close()

    def test_invalid_uploads_are_rejected_and_do_not_leave_files(self):
        corrupt_png = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aWQAAAABJRU5ErkJggg==')
        for name, data in [('bad.html', b'<script>bad()</script>'), ('fake.png', b'not an image'), ('corrupt.png', corrupt_png), ('bad.pdf', b'%PDF-bad'), ('empty.zip', b'')]:
            self.assertEqual(self.upload(name, data).status_code, 400)
        self.assertEqual(list((Path(self.storage.name) / 'guide-files').iterdir()), [])

    def test_large_html_and_invalid_title_are_rejected(self):
        self.assertEqual(self.save('<p>正常正文</p>', title='').status_code, 400)
        self.assertEqual(self.save('<p>' + 'x' * 1048576 + '</p>').status_code, 400)
        self.assertEqual(self.visitor.get('/guides/catalog.json').json[0]['title'], '参数手册')

    def test_editor_csp_does_not_weaken_other_admin_pages(self):
        editor = self.client.get('/admin/guides/example/edit')
        self.assertIn("style-src 'self' 'unsafe-inline'", editor.headers['Content-Security-Policy'])
        self.assertIn("script-src 'self';", editor.headers['Content-Security-Policy'])
        self.assertNotIn('unsafe-inline', self.client.get('/admin/').headers['Content-Security-Policy'])


if __name__ == '__main__':
    unittest.main()
