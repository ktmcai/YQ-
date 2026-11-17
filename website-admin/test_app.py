import io
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from pypdf import PdfWriter
from werkzeug.security import generate_password_hash

from app import create_app


class DocumentManagementTests(unittest.TestCase):
    def setUp(self):
        self.storage = tempfile.TemporaryDirectory()
        self.config = {"TESTING": True, "SECRET_KEY": "test-only-secret", "DATA_DIR": self.storage.name, "SESSION_COOKIE_SECURE": False}
        self.app = create_app(self.config)
        self.client = self.app.test_client()
        self.visitor = self.app.test_client()
        with sqlite3.connect(Path(self.storage.name) / "documents.sqlite") as connection:
            connection.execute("INSERT INTO admin (id,password_hash) VALUES (1,?)", (generate_password_hash("initial-password-123"),))
        connection.close()

    def tearDown(self):
        self.storage.cleanup()

    def csrf(self, client=None):
        client = client or self.client
        client.get("/admin/login")
        with client.session_transaction() as session:
            return session["csrf"]

    def login(self, client=None, password="initial-password-123"):
        client = client or self.client
        return client.post("/admin/login", data={"username": "admin", "password": password, "csrf_token": self.csrf(client)})

    def token(self):
        self.client.get("/admin/")
        with self.client.session_transaction() as session:
            return session["csrf"]

    def pdf(self, encrypted=False, padding=False):
        writer = PdfWriter()
        writer.add_blank_page(width=595, height=842)
        if padding:
            writer.add_metadata({"/TestPadding": "x" * 400000})
        if encrypted:
            writer.encrypt("password")
        stream = io.BytesIO()
        writer.write(stream)
        return stream.getvalue()

    def upload(self, published=True, title="产品用户手册", content=None, filename="用户手册.pdf", route="/admin/new"):
        return self.client.post(route, data={"csrf_token": self.token(), "title": title, "action": "publish" if published else "draft", "pdf": (io.BytesIO(self.pdf() if content is None else content), filename)}, content_type="multipart/form-data")

    def post(self, route, **data):
        return self.client.post(route, data={"csrf_token": self.token(), **data})

    def test_admin_routes_require_login(self):
        for route in ("/admin/", "/admin/new", "/admin/password", "/admin/documents/1/edit"):
            self.assertEqual(self.visitor.get(route).status_code, 302)
        response = self.visitor.post("/admin/new", data={"title": "unauthorized"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(list((Path(self.storage.name) / "files").iterdir()), [])

    def test_login_csrf_and_cookie_flags(self):
        self.assertEqual(self.client.post("/admin/login", data={"username": "admin", "password": "initial-password-123"}).status_code, 400)
        token = self.csrf()
        self.assertEqual(self.client.post("/admin/login", data={"csrf_token": "非有效令牌"}).status_code, 400)
        self.assertEqual(self.client.post("/admin/login", data={"csrf_token": token, "username": "admin", "password": "wrong"}).status_code, 401)
        response = self.login()
        self.assertEqual(response.status_code, 302)
        cookie = response.headers["Set-Cookie"]
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Strict", cookie)
        self.assertEqual(self.client.get("/admin/").status_code, 200)

    def test_login_rate_limit(self):
        for _ in range(5):
            self.assertEqual(self.login(password="wrong").status_code, 401)
        self.assertEqual(self.login().status_code, 429)

    def test_invalid_or_disguised_pdf_rejected_and_cleaned(self):
        self.login()
        for payload, filename in ((b"<script>bad</script>", "fake.pdf"), (self.pdf(), "file.html"), (b"%PDF-not-a-document", "bad.pdf")):
            self.assertEqual(self.upload(content=payload, filename=filename).status_code, 400)
        self.assertEqual(list((Path(self.storage.name) / "files").iterdir()), [])
        self.assertEqual(self.visitor.get("/api/documents").json, [])

    def test_encrypted_pdf_rejected(self):
        self.login()
        self.assertEqual(self.upload(content=self.pdf(encrypted=True)).status_code, 400)
        self.assertEqual(list((Path(self.storage.name) / "files").iterdir()), [])

    def test_request_size_limit(self):
        self.login()
        self.app.config["MAX_CONTENT_LENGTH"] = 1024
        response = self.upload(content=b"x" * 2048)
        self.assertEqual(response.status_code, 413)

    def test_real_multipart_pdf_larger_than_parser_buffer(self):
        self.login()
        self.assertEqual(self.upload(content=self.pdf(padding=True)).status_code, 302)
        self.assertGreater(self.visitor.get("/api/documents").json[0]["byte_size"], 256 * 1024)

    def test_draft_publish_download_unpublish_and_delete(self):
        self.login()
        self.assertEqual(self.upload(published=False).status_code, 302)
        self.assertEqual(self.visitor.get("/api/documents").json, [])
        for route in ("/api/documents/1", "/documents/1/view", "/documents/1/download"):
            self.assertEqual(self.visitor.get(route).status_code, 404)
        preview = self.client.get("/documents/1/view")
        self.assertEqual(preview.status_code, 200)
        preview.close()
        self.post("/admin/documents/1/visibility")
        metadata = self.visitor.get("/api/documents").json[0]
        self.assertEqual(metadata["title"], "产品用户手册")
        self.assertEqual(metadata["page_count"], 1)
        self.assertNotIn("stored_name", metadata)
        view = self.visitor.get("/documents/1/view")
        self.assertEqual(view.mimetype, "application/pdf")
        self.assertTrue(view.headers["Content-Disposition"].startswith("inline"))
        self.assertEqual(view.headers["X-Content-Type-Options"], "nosniff")
        view.close()
        download = self.visitor.get("/documents/1/download")
        self.assertTrue(download.headers["Content-Disposition"].startswith("attachment"))
        self.assertTrue(download.data.startswith(b"%PDF-"))
        download.close()
        partial = self.visitor.get("/documents/1/view", headers={"Range": "bytes=0-4"})
        self.assertEqual(partial.status_code, 206)
        self.assertEqual(partial.data, b"%PDF-")
        partial.close()
        self.post("/admin/documents/1/visibility")
        self.assertEqual(self.visitor.get("/documents/1/download").status_code, 404)
        self.post("/admin/documents/1/delete")
        self.assertEqual(self.client.get("/api/documents/1").status_code, 404)
        self.assertEqual(list((Path(self.storage.name) / "files").iterdir()), [])

    def test_rename_replace_and_keep_public_url(self):
        self.login()
        self.upload()
        old_file = next((Path(self.storage.name) / "files").iterdir())
        renamed = self.post("/admin/documents/1/edit", title="新名称", action="publish")
        self.assertEqual(renamed.status_code, 302)
        self.assertTrue(old_file.exists())
        self.assertEqual(self.visitor.get("/api/documents/1").json["title"], "新名称")
        self.assertEqual(self.upload(title="替换版本", filename="新版.pdf", route="/admin/documents/1/edit").status_code, 302)
        self.assertFalse(old_file.exists())
        self.assertEqual(len(list((Path(self.storage.name) / "files").iterdir())), 1)
        self.assertEqual(self.visitor.get("/api/documents/1").json["original_name"], "新版.pdf")

    def test_titles_are_escaped_and_upload_paths_are_not_used(self):
        self.login()
        self.upload(title='<img src=x onerror="alert(1)">', filename="../../outside.pdf")
        page = self.client.get("/admin/").get_data(as_text=True)
        self.assertIn("&lt;img", page)
        self.assertNotIn('<img src=x', page)
        item = self.visitor.get("/api/documents/1").json
        self.assertEqual(item["original_name"], "outside.pdf")
        stored = next((Path(self.storage.name) / "files").iterdir())
        self.assertRegex(stored.name, r"^[a-f0-9]{32}\.pdf$")

    def test_password_change_invalidates_all_sessions(self):
        self.login()
        second = self.app.test_client()
        self.login(second)
        result = self.post("/admin/password", current_password="initial-password-123", new_password="changed-password-456", confirm_password="changed-password-456")
        self.assertEqual(result.status_code, 302)
        self.assertEqual(second.get("/admin/").status_code, 302)
        self.assertEqual(self.client.get("/admin/").status_code, 302)
        self.assertEqual(self.login(password="changed-password-456").status_code, 302)

    def test_document_data_survives_application_restart(self):
        self.login()
        self.upload()
        restarted = create_app(self.config).test_client()
        self.assertEqual(restarted.get("/api/documents").json[0]["title"], "产品用户手册")
        response = restarted.get("/documents/1/download")
        self.assertEqual(response.status_code, 200)
        response.close()

    def test_link_document_draft_publish_edit_unpublish_delete(self):
        self.login()
        fields = {"title": "选型文档", "source_type": "url", "external_url": "https://example.com/wiki?doc=panels", "action": "draft"}
        self.assertEqual(self.post("/admin/new", **fields).status_code, 302)
        self.assertEqual(self.visitor.get("/api/documents").json, [])
        self.assertEqual(self.visitor.get("/api/documents/1").status_code, 404)
        self.assertEqual(self.client.get("/api/documents/1").json["source_type"], "url")
        self.post("/admin/documents/1/visibility")
        item = self.visitor.get("/api/documents").json[0]
        self.assertEqual(item["external_url"], fields["external_url"])
        self.assertEqual(item["byte_size"], 0)
        for action in ("view", "download"):
            self.assertEqual(self.visitor.get(f"/documents/1/{action}").status_code, 404)
        fields.update(title="新名称", external_url="https://example.com/new", action="publish")
        self.assertEqual(self.post("/admin/documents/1/edit", **fields).status_code, 302)
        page = self.client.get("/admin/documents/1/edit").get_data(as_text=True)
        self.assertIn('value="https://example.com/new"', page)
        self.assertIn('value="url" selected', page)
        self.assertEqual(self.visitor.get("/api/documents/1").json["title"], "新名称")
        self.post("/admin/documents/1/visibility")
        self.assertEqual(self.visitor.get("/api/documents").json, [])
        self.assertEqual(self.post("/admin/documents/1/delete").status_code, 302)
        self.assertEqual(list((Path(self.storage.name) / "files").iterdir()), [])

    def test_link_document_invalid_urls_and_types_are_rejected(self):
        self.login()
        for url in ("", "javascript:alert(1)", "data:text/html,bad", "//example.com", "/manual", "https://", "https://example.com/\nattack", "https://example.com/\\attack", "https://user:password@example.com", "https://[broken"):
            result = self.post("/admin/new", title="链接资料", source_type="url", external_url=url, action="publish")
            self.assertEqual(result.status_code, 400, url)
        self.assertEqual(self.post("/admin/new", title="链接资料", source_type="invalid", action="publish").status_code, 400)
        self.assertEqual(self.visitor.get("/api/documents").json, [])
        self.assertEqual(list((Path(self.storage.name) / "files").iterdir()), [])

    def test_switch_document_types_cleans_files_and_requires_new_pdf(self):
        self.login()
        self.upload()
        old_file = next((Path(self.storage.name) / "files").iterdir())
        fields = {"title": "网页版本", "source_type": "url", "external_url": "https://example.com/manual", "action": "publish"}
        self.assertEqual(self.post("/admin/documents/1/edit", **fields).status_code, 302)
        self.assertFalse(old_file.exists())
        self.assertEqual(self.visitor.get("/documents/1/download").status_code, 404)
        self.assertEqual(self.post("/admin/documents/1/edit", title="PDF 版本", source_type="pdf", action="publish").status_code, 400)
        self.assertEqual(self.visitor.get("/api/documents/1").json["source_type"], "url")
        result = self.client.post("/admin/documents/1/edit", data={"csrf_token": self.token(), "title": "PDF 版本", "source_type": "pdf", "external_url": "javascript:ignored", "action": "publish", "pdf": (io.BytesIO(self.pdf()), "new.pdf")})
        self.assertEqual(result.status_code, 302)
        item = self.visitor.get("/api/documents/1").json
        self.assertEqual((item["source_type"], item["external_url"], item["original_name"]), ("pdf", "", "new.pdf"))
        download = self.visitor.get("/documents/1/download")
        self.assertEqual(download.status_code, 200)
        download.close()
        self.assertEqual(len(list((Path(self.storage.name) / "files").iterdir())), 1)

    def test_pdf_upload_is_ignored_when_link_type_selected(self):
        self.login()
        result = self.client.post("/admin/new", data={"csrf_token": self.token(), "title": "网页资料", "source_type": "url", "external_url": "https://example.com", "action": "publish", "pdf": (io.BytesIO(b"not-pdf"), "ignored.txt")})
        self.assertEqual(result.status_code, 302)
        self.assertEqual(list((Path(self.storage.name) / "files").iterdir()), [])

    def test_legacy_pdf_schema_migrates_without_changing_data(self):
        with tempfile.TemporaryDirectory() as storage:
            files = Path(storage) / "files"
            files.mkdir()
            content = self.pdf()
            (files / "existing.pdf").write_bytes(content)
            connection = sqlite3.connect(Path(storage) / "documents.sqlite")
            with connection:
                connection.execute("CREATE TABLE documents (id INTEGER PRIMARY KEY AUTOINCREMENT,title TEXT NOT NULL,stored_name TEXT NOT NULL,original_name TEXT NOT NULL,byte_size INTEGER NOT NULL,page_count INTEGER NOT NULL,published INTEGER NOT NULL DEFAULT 0,updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
                connection.execute("INSERT INTO documents (id,title,stored_name,original_name,byte_size,page_count,published) VALUES (2,'已有资料','existing.pdf','原手册.pdf',?,1,1)", (len(content),))
            connection.close()
            config = {**self.config, "DATA_DIR": storage}
            migrated = create_app(config).test_client()
            item = migrated.get("/api/documents/2").json
            self.assertEqual((item["id"], item["source_type"], item["external_url"], item["title"]), (2, "pdf", "", "已有资料"))
            download = migrated.get("/documents/2/download")
            self.assertEqual(download.data, content)
            download.close()
            self.assertEqual(create_app(config).test_client().get("/api/documents/2").json, item)

    def product_form(self, **changes):
        values = {"name": "新增产品", "description": "产品简介", "description_en": "Product description", "category_id": "1", "series": "JP", "sort_order": "5", "link_type": "url", "url": "https://example.com/manual", "document_id": "", "action": "publish"}
        values.update(changes)
        return values

    def public_product(self, name):
        return next((item for group in self.visitor.get("/api/products").json for item in group["products"] if item["name"] == name), None)

    def test_existing_catalog_migrates_once_without_changes(self):
        seed = json.loads(Path(__file__).with_name("catalog.json").read_text(encoding="utf-8"))
        actual = self.visitor.get("/api/products").json
        self.assertEqual(len(actual), 6)
        self.assertEqual(sum(len(group["products"]) for group in actual), 8)
        for expected, group in zip(seed, actual):
            for key in ("name", "description", "description_en", "wide"):
                self.assertEqual(expected[key], group[key])
            self.assertEqual([item["url"] for item in expected["products"]], [item["href"] for item in group["products"]])
        restarted = create_app(self.config).test_client()
        self.assertEqual(restarted.get("/api/products").json, actual)

    def test_product_management_requires_authentication_and_csrf(self):
        for route in ("/admin/products", "/admin/products/new", "/admin/products/1/edit"):
            self.assertEqual(self.visitor.get(route).status_code, 302)
        for route in ("/admin/products/new", "/admin/products/1/visibility", "/admin/products/1/delete"):
            self.assertEqual(self.visitor.post(route).status_code, 302)
        self.login()
        self.assertEqual(self.client.post("/admin/products/new", data=self.product_form()).status_code, 400)
        self.assertEqual(self.client.get("/admin/products/1/delete").status_code, 405)

    def test_product_torque_save_edit_clear_and_restart(self):
        self.login()
        self.assertEqual(self.post('/admin/products/new', **self.product_form(rated_torque='2.5', peak_torque='6')).status_code, 302)
        item = self.public_product('新增产品')
        self.assertEqual((item['rated_torque'], item['peak_torque']), ('2.5', '6'))
        page = self.client.get(f"/admin/products/{item['id']}/edit").get_data(as_text=True)
        self.assertIn('name="rated_torque" value="2.5"', page)
        self.assertEqual(self.post(f"/admin/products/{item['id']}/edit", **self.product_form(rated_torque='0', peak_torque='')).status_code, 302)
        restarted = create_app(self.config).test_client().get('/api/products').json
        saved = next(p for group in restarted for p in group['products'] if p['id'] == item['id'])
        self.assertEqual((saved['rated_torque'], saved['peak_torque']), ('0', ''))
        self.assertEqual(self.post(f"/admin/products/{item['id']}/edit", **self.product_form()).status_code, 302)
        cleared = self.public_product('新增产品')
        self.assertEqual((cleared['rated_torque'], cleared['peak_torque']), ('', ''))

    def test_product_torque_rejects_invalid_values(self):
        self.login()
        for field in ('rated_torque', 'peak_torque'):
            for value in ('-1', 'NaN', 'Infinity', '1e3', '6 N·m', '<script>', '1234567890123'):
                with self.subTest(field=field, value=value):
                    self.assertEqual(self.post('/admin/products/new', **self.product_form(**{field: value})).status_code, 400)
        self.assertIsNone(self.public_product('新增产品'))

    def test_product_torque_migration_preserves_existing_data(self):
        before = self.visitor.get('/api/products').json
        with sqlite3.connect(Path(self.storage.name) / 'documents.sqlite') as connection:
            columns = ','.join(row[1] for row in connection.execute('PRAGMA table_info(products)') if row[1] not in ('rated_torque', 'peak_torque'))
            connection.execute(f'CREATE TABLE legacy_products AS SELECT {columns} FROM products')
            connection.execute('DROP TABLE products')
            connection.execute('ALTER TABLE legacy_products RENAME TO products')
        connection.close()
        restarted = create_app(self.config).test_client()
        self.assertEqual(restarted.get('/api/products').json, before)

    def test_axis_series_migration_selection_and_category_move(self):
        groups = self.visitor.get('/api/products').json
        self.assertEqual([row['code'] for row in groups[0]['series']], ['JP', 'JS', 'JC'])
        self.assertTrue(all(row['series'] == 'JP' for row in groups[0]['products']))
        self.assertTrue(all(not group['series'] for group in groups[1:]))
        self.login()
        self.assertEqual(self.post('/admin/products/new', **self.product_form(series='JS')).status_code, 302)
        self.assertEqual(self.public_product('新增产品')['series'], 'JS')
        restarted = create_app(self.config).test_client()
        self.assertEqual(restarted.get('/api/products').json[0]['products'][1]['series'], 'JS')
        self.assertEqual(self.post('/admin/products/9/edit', **self.product_form(category_id='2', series='JC')).status_code, 302)
        self.assertEqual(self.public_product('新增产品')['series'], '')
        for series in ['', 'UNKNOWN']:
            self.assertEqual(self.post('/admin/products/new', **self.product_form(series=series)).status_code, 400)

    def test_product_draft_publish_sort_move_and_delete(self):
        self.login()
        self.assertEqual(self.post("/admin/products/new", **self.product_form(action="draft")).status_code, 302)
        self.assertIsNone(self.public_product("新增产品"))
        self.post("/admin/products/9/visibility")
        products = self.visitor.get("/api/products").json[0]["products"]
        self.assertEqual(products[1]["name"], "新增产品")
        self.assertEqual(self.public_product("新增产品")["href"], "https://example.com/manual")
        self.post("/admin/products/9/edit", **self.product_form(name="已移动产品", category_id="2", link_type="none"))
        group = self.visitor.get("/api/products").json[1]
        self.assertEqual(group["products"][0]["name"], "已移动产品")
        self.assertIsNone(group["products"][0]["href"])
        self.post("/admin/products/9/visibility")
        self.assertIsNone(self.public_product("已移动产品"))
        self.post("/admin/products/9/delete")
        self.assertEqual(self.client.get("/admin/products/9/edit").status_code, 404)

    def test_product_invalid_links_and_fields_are_rejected(self):
        self.login()
        for url in ("javascript:alert(1)", "data:text/html,bad", "//example.com", "/\\example.com", "https://", "https://example.com/\nattack"):
            self.assertEqual(self.post("/admin/products/new", **self.product_form(url=url)).status_code, 400)
        for fields in ({"name": ""}, {"sort_order": "-1"}, {"sort_order": "invalid"}, {"category_id": "999"}, {"link_type": "invalid"}, {"link_type": "pdf", "document_id": "999"}):
            self.assertEqual(self.post("/admin/products/new", **self.product_form(**fields)).status_code, 400)
        self.assertEqual(sum(len(group["products"]) for group in self.visitor.get("/api/products").json), 8)

    def test_product_pdf_respects_document_publication_and_deletion(self):
        self.login()
        self.upload(published=False)
        fields = self.product_form(link_type="pdf", document_id="1")
        self.assertEqual(self.post("/admin/products/new", **fields).status_code, 400)
        self.assertEqual(self.post("/admin/products/new", **self.product_form(link_type="pdf", document_id="1", action="draft")).status_code, 302)
        self.post("/admin/products/9/visibility")
        self.assertIsNone(self.public_product("新增产品"))
        self.post("/admin/documents/1/visibility")
        self.post("/admin/products/9/visibility")
        self.assertEqual(self.public_product("新增产品")["href"], "/document.html?id=1")
        self.post("/admin/documents/1/visibility")
        self.assertIsNone(self.public_product("新增产品")["href"])
        self.post("/admin/documents/1/delete")
        self.assertIsNone(self.public_product("新增产品")["href"])
        self.assertIn("关联 PDF 已删除", self.client.get("/admin/products").get_data(as_text=True))

    def test_link_documents_cannot_be_selected_as_product_pdfs(self):
        self.login()
        self.post("/admin/new", title="链接资料", source_type="url", external_url="https://example.com/manual", action="publish")
        page = self.client.get("/admin/products/new").get_data(as_text=True)
        self.assertNotIn("链接资料", page)
        result = self.post("/admin/products/new", **self.product_form(link_type="pdf", document_id="1"))
        self.assertEqual(result.status_code, 400)

    def test_associated_pdf_cannot_switch_to_link_until_unlinked(self):
        self.login()
        self.upload()
        old_file = next((Path(self.storage.name) / "files").iterdir())
        self.post("/admin/products/new", **self.product_form(link_type="pdf", document_id="1"))
        fields = {"title": "网页资料", "source_type": "url", "external_url": "https://example.com/manual", "action": "publish"}
        result = self.post("/admin/documents/1/edit", **fields)
        self.assertEqual(result.status_code, 400)
        self.assertIn("已关联产品", result.get_data(as_text=True))
        self.assertTrue(old_file.exists())
        self.assertEqual(self.public_product("新增产品")["href"], "/document.html?id=1")
        self.post("/admin/products/9/edit", **self.product_form(link_type="none"))
        self.assertEqual(self.post("/admin/documents/1/edit", **fields).status_code, 302)
        self.assertFalse(old_file.exists())

    def test_product_titles_are_escaped_and_internal_links_work(self):
        self.login()
        name = '<img src=x onerror="alert(1)">'
        self.post("/admin/products/new", **self.product_form(name=name, url="/document.html?id=1"))
        page = self.client.get("/admin/products").get_data(as_text=True)
        self.assertIn("&lt;img", page)
        self.assertNotIn('<img src=x', page)
        self.assertFalse(self.public_product(name)["external"])

    def test_deleted_products_do_not_reappear_after_restart(self):
        self.login()
        for product_id in range(1, 9):
            self.post(f"/admin/products/{product_id}/delete")
        restarted = create_app(self.config).test_client()
        groups = restarted.get("/api/products").json
        self.assertEqual(len(groups), 6)
        self.assertTrue(all(not group["products"] for group in groups))


if __name__ == "__main__":
    unittest.main()
