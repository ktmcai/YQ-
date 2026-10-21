import hmac
import os
import re
import secrets
import sqlite3
import sys
import tempfile
import time
from datetime import timedelta
from pathlib import Path
from uuid import uuid4
from urllib.parse import urlsplit

from flask import (
    Flask, abort, flash, g, jsonify, redirect, render_template, request,
    send_file, session, url_for,
)
from pypdf import PdfReader
from pypdf.errors import PdfReadError
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash, generate_password_hash

from products import register_products


def create_app(config=None):
    app = Flask(__name__, static_url_path="/admin/assets")
    app.config.update(
        SECRET_KEY=os.environ.get("YONIQ_SECRET_KEY"),
        DATA_DIR=os.environ.get("YONIQ_DATA_DIR", "/var/lib/yoniq-docs"),
        MAX_CONTENT_LENGTH=32 * 1024 * 1024,
        MAX_FORM_MEMORY_SIZE=256 * 1024,
        MAX_FORM_PARTS=12,
        SESSION_COOKIE_NAME="yoniq_admin",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Strict",
        SESSION_COOKIE_SECURE=os.environ.get("YONIQ_COOKIE_SECURE", "1") == "1",
        PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
        TRUSTED_HOSTS=["yoniqtech.com", "www.yoniqtech.com", "127.0.0.1", "localhost", "120.79.178.50"],
    )
    if config:
        app.config.update(config)
    if not app.secret_key:
        raise RuntimeError("YONIQ_SECRET_KEY must be configured")
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)
    data_dir = Path(app.config["DATA_DIR"])
    files_dir = data_dir / "files"
    files_dir.mkdir(parents=True, exist_ok=True)

    def db():
        if "db" not in g:
            g.db = sqlite3.connect(data_dir / "documents.sqlite", timeout=10)
            g.db.row_factory = sqlite3.Row
            g.db.execute("PRAGMA foreign_keys=ON")
        return g.db

    @app.teardown_appcontext
    def close_db(error):
        connection = g.pop("db", None)
        if connection:
            connection.close()

    with app.app_context():
        db().executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS admin (
                id INTEGER PRIMARY KEY CHECK (id=1),
                password_hash TEXT NOT NULL,
                auth_version INTEGER NOT NULL DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                stored_name TEXT NOT NULL,
                original_name TEXT NOT NULL,
                byte_size INTEGER NOT NULL,
                page_count INTEGER NOT NULL,
                published INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS login_failures (ip TEXT NOT NULL, attempted_at REAL NOT NULL);
            CREATE INDEX IF NOT EXISTS login_failures_ip_time ON login_failures(ip, attempted_at);
        """)
        columns = {row["name"] for row in db().execute("PRAGMA table_info(documents)")}
        with db():
            if "source_type" not in columns:
                db().execute("ALTER TABLE documents ADD COLUMN source_type TEXT NOT NULL DEFAULT 'pdf'")
            if "external_url" not in columns:
                db().execute("ALTER TABLE documents ADD COLUMN external_url TEXT NOT NULL DEFAULT ''")

    def csrf_token():
        if "csrf" not in session:
            session["csrf"] = secrets.token_urlsafe(32)
        return session["csrf"]

    app.jinja_env.globals["csrf_token"] = csrf_token

    @app.before_request
    def authenticate():
        g.admin = False
        if session.get("authenticated"):
            admin = db().execute("SELECT auth_version FROM admin WHERE id=1").fetchone()
            g.admin = bool(admin and session.get("auth_version") == admin["auth_version"])
        if request.path.startswith("/admin") and request.endpoint not in ("login", "static") and not g.admin:
            return redirect(url_for("login"))
        if request.method == "POST":
            expected = session.get("csrf", "")
            submitted = request.form.get("csrf_token", "")
            if not expected or not hmac.compare_digest(expected.encode(), submitted.encode()):
                abort(400, description="页面已过期，请刷新后重试。")

    @app.after_request
    def headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Cache-Control"] = "no-store"
        if request.path.startswith("/admin"):
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; script-src 'self'; style-src 'self'; "
                "base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
            )
        return response

    @app.errorhandler(HTTPException)
    def request_error(error):
        if request.path.startswith("/api/"):
            return jsonify(error=error.description), error.code
        message = "PDF 文件太大，请使用不超过 30 MB 的文件。" if error.code == 413 else error.description
        return render_template("error.html", message=message, status=error.code), error.code

    @app.route("/admin/login", methods=["GET", "POST"])
    def login():
        if g.admin:
            return redirect(url_for("dashboard"))
        error = None
        if request.method == "POST":
            cutoff = time.time() - 900
            ip = request.remote_addr
            with db():
                db().execute("DELETE FROM login_failures WHERE attempted_at < ?", (cutoff,))
            failures = db().execute("SELECT count(*) FROM login_failures WHERE ip=?", (ip,)).fetchone()[0]
            if failures >= 5:
                return render_template("login.html", error="登录失败次数过多，请在 15 分钟后重试。"), 429
            admin = db().execute("SELECT * FROM admin WHERE id=1").fetchone()
            password = request.form.get("password", "")
            if admin and request.form.get("username") == "admin" and check_password_hash(admin["password_hash"], password):
                with db():
                    db().execute("DELETE FROM login_failures WHERE ip=?", (ip,))
                session.clear()
                session.update(authenticated=True, auth_version=admin["auth_version"])
                session.permanent = True
                return redirect(url_for("dashboard"))
            with db():
                db().execute("INSERT INTO login_failures VALUES (?, ?)", (ip, time.time()))
            error = "账号或密码不正确，请重新输入。"
        return render_template("login.html", error=error), 401 if error else 200

    @app.post("/admin/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))

    @app.route("/admin/password", methods=["GET", "POST"])
    def password():
        error = None
        if request.method == "POST":
            admin = db().execute("SELECT * FROM admin WHERE id=1").fetchone()
            new_password = request.form.get("new_password", "")
            if not check_password_hash(admin["password_hash"], request.form.get("current_password", "")):
                error = "当前密码不正确。"
            elif not 12 <= len(new_password) <= 128:
                error = "新密码需要 12 至 128 个字符。"
            elif new_password != request.form.get("confirm_password"):
                error = "两次输入的新密码不一致。"
            else:
                with db():
                    db().execute("UPDATE admin SET password_hash=?, auth_version=auth_version+1 WHERE id=1", (generate_password_hash(new_password),))
                session.clear()
                flash("密码已修改，请使用新密码登录。", "success")
                return redirect(url_for("login"))
        return render_template("password.html", error=error), 400 if error else 200

    @app.get("/admin/")
    def dashboard():
        documents = db().execute("SELECT * FROM documents ORDER BY id DESC").fetchall()
        return render_template("dashboard.html", documents=documents)

    def document(document_id):
        item = db().execute("SELECT * FROM documents WHERE id=?", (document_id,)).fetchone()
        if not item:
            abort(404, description="这份文档不存在或已删除。")
        return item

    def store_pdf(upload):
        original_name = re.sub(r"[\x00-\x1f\x7f]", "", upload.filename.replace("\\", "/").split("/")[-1])[:180]
        if not original_name.lower().endswith(".pdf"):
            raise ValueError("请选择 PDF 格式的文件。")
        stored_name = uuid4().hex + ".pdf"
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=files_dir, suffix=".upload", delete=False) as target:
                temporary = Path(target.name)
                size = 0
                while chunk := upload.stream.read(65536):
                    size += len(chunk)
                    if size > 30 * 1024 * 1024:
                        raise ValueError("PDF 文件不能超过 30 MB。")
                    target.write(chunk)
            with temporary.open("rb") as source:
                if source.read(5) != b"%PDF-":
                    raise ValueError("文件内容不是有效的 PDF，请重新导出后上传。")
                source.seek(0)
                try:
                    pdf = PdfReader(source)
                    if pdf.is_encrypted:
                        raise ValueError("请上传未加密、无需密码即可查看的 PDF。")
                    pages = len(pdf.pages)
                except PdfReadError as error:
                    raise ValueError("无法读取这份 PDF，请重新导出后上传。") from error
            if pages == 0:
                raise ValueError("PDF 至少需要包含一页内容。")
            os.replace(temporary, files_dir / stored_name)
            temporary = None
            return stored_name, original_name, size, pages
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    @app.route("/admin/new", methods=["GET", "POST"])
    @app.route("/admin/documents/<int:document_id>/edit", methods=["GET", "POST"])
    def edit(document_id=None):
        item = document(document_id) if document_id is not None else None
        error = None
        title = request.form.get("title", "").strip() if request.method == "POST" else item["title"] if item else ""
        source_type = request.form.get("source_type", item["source_type"] if item else "pdf")
        external_url = request.form.get("external_url", item["external_url"] if item else "").strip()
        if request.method == "POST":
            saved = None
            try:
                if not 1 <= len(title) <= 120:
                    raise ValueError("文档名称需要 1 至 120 个字符。")
                if source_type not in ("pdf", "url"):
                    raise ValueError("请选择 PDF 文件或网页链接。")
                if source_type == "url":
                    if not external_url or len(external_url) > 2048 or re.search(r"[\x00-\x20\x7f\\]", external_url):
                        raise ValueError("请填写有效的网页链接地址。")
                    parsed = urlsplit(external_url)
                    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
                        raise ValueError("网页链接需以 https:// 或 http:// 开头，且不包含账号密码。")
                    if item and item["source_type"] == "pdf" and db().execute("SELECT 1 FROM products WHERE document_id=? LIMIT 1", (document_id,)).fetchone():
                        raise ValueError("这份 PDF 已关联产品，请先在产品管理中修改关联，再切换为网页链接。")
                    fields = ("", "", 0, 0)
                else:
                    external_url = ""
                    upload = request.files.get("pdf")
                    if upload and upload.filename:
                        saved = store_pdf(upload)
                    elif item is None or item["source_type"] != "pdf":
                        raise ValueError("请选择要上传的 PDF 文件。")
                    fields = saved or tuple(item[key] for key in ("stored_name", "original_name", "byte_size", "page_count"))
                published = int(request.form.get("action") == "publish")
                with db():
                    if item:
                        db().execute("UPDATE documents SET title=?, stored_name=?, original_name=?, byte_size=?, page_count=?, published=?, source_type=?, external_url=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (title, *fields, published, source_type, external_url, document_id))
                    else:
                        db().execute("INSERT INTO documents (title, stored_name, original_name, byte_size, page_count, published, source_type, external_url) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (title, *fields, published, source_type, external_url))
                if item and item["stored_name"] and (saved or source_type == "url"):
                    (files_dir / item["stored_name"]).unlink(missing_ok=True)
                flash("文档已发布，官网资料卡片会自动更新。" if published else "草稿已保存，访客暂时看不到这份文档。", "success")
                return redirect(url_for("dashboard"))
            except ValueError as problem:
                error = str(problem)
            except sqlite3.Error:
                if saved:
                    (files_dir / saved[0]).unlink(missing_ok=True)
                raise
        return render_template("edit.html", document=item, title=title, source_type=source_type, external_url=external_url, error=error), 400 if error else 200

    @app.post("/admin/documents/<int:document_id>/visibility")
    def visibility(document_id):
        item = document(document_id)
        with db():
            db().execute("UPDATE documents SET published=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (1 - item["published"], document_id))
        flash("文档已下架，访客无法查看或下载。" if item["published"] else "文档已发布。", "success")
        return redirect(url_for("dashboard"))

    @app.post("/admin/documents/<int:document_id>/delete")
    def delete(document_id):
        item = document(document_id)
        with db():
            db().execute("DELETE FROM documents WHERE id=?", (document_id,))
        if item["stored_name"]:
            (files_dir / item["stored_name"]).unlink(missing_ok=True)
        flash("文档已删除。", "success")
        return redirect(url_for("dashboard"))

    def public_document(item):
        return {key: item[key] for key in ("id", "title", "original_name", "byte_size", "page_count", "source_type", "external_url")}

    @app.get("/api/documents")
    def list_documents():
        items = db().execute("SELECT * FROM documents WHERE published=1 ORDER BY id DESC").fetchall()
        return jsonify([public_document(item) for item in items])

    def visible_document(document_id):
        item = document(document_id)
        if not item["published"] and not g.admin:
            abort(404, description="这份文档尚未发布或已经下架。")
        return item

    @app.get("/api/documents/<int:document_id>")
    def document_details(document_id):
        return jsonify(public_document(visible_document(document_id)))

    @app.get("/documents/<int:document_id>/view")
    @app.get("/documents/<int:document_id>/download")
    def pdf_file(document_id):
        item = visible_document(document_id)
        if item["source_type"] != "pdf":
            abort(404, description="这份资料是网页链接，没有可下载的 PDF 文件。")
        return send_file(files_dir / item["stored_name"], mimetype="application/pdf", as_attachment=request.path.endswith("/download"), download_name=item["original_name"], conditional=True)

    register_products(app, db)
    return app


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("init-admin", "reset-password"):
        raise SystemExit("Usage: python app.py init-admin|reset-password (read password from stdin)")
    application = create_app()
    password_value = sys.stdin.readline().rstrip("\r\n")
    if not 12 <= len(password_value) <= 128:
        raise SystemExit("Password must contain 12 to 128 characters")
    connection = sqlite3.connect(Path(application.config["DATA_DIR"]) / "documents.sqlite")
    with connection:
        if sys.argv[1] == "init-admin":
            connection.execute("INSERT INTO admin (id, password_hash) VALUES (1, ?)", (generate_password_hash(password_value),))
        else:
            if connection.execute("UPDATE admin SET password_hash=?, auth_version=auth_version+1 WHERE id=1", (generate_password_hash(password_value),)).rowcount != 1:
                raise SystemExit("Admin account has not been initialized")
    connection.close()
    print("Admin credentials saved as a password hash.")
