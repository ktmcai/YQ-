import json
import re
from pathlib import Path
from urllib.parse import urlsplit

from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, url_for
from taxonomy import AXIS, AXIS_SERIES


def register_products(app, db):
    catalog = Blueprint("catalog", __name__)
    with app.app_context():
        db().executescript("""
            CREATE TABLE IF NOT EXISTS product_categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                description_en TEXT NOT NULL DEFAULT '',
                wide INTEGER NOT NULL DEFAULT 0,
                sort_order INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category_id INTEGER NOT NULL REFERENCES product_categories(id) ON DELETE RESTRICT,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                description_en TEXT NOT NULL DEFAULT '',
                link_type TEXT NOT NULL CHECK (link_type IN ('url','pdf','none')),
                url TEXT NOT NULL DEFAULT '',
                document_id INTEGER REFERENCES documents(id) ON DELETE SET NULL,
                sort_order INTEGER NOT NULL DEFAULT 0,
                published INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS catalog_migrations (name TEXT PRIMARY KEY);
        """)
        with db():
            if not db().execute("SELECT 1 FROM catalog_migrations WHERE name='initial'").fetchone():
                seed = json.loads(Path(__file__).with_name("catalog.json").read_text(encoding="utf-8"))
                for index, category in enumerate(seed):
                    db().execute("INSERT INTO product_categories (id,name,description,description_en,wide,sort_order) VALUES (?,?,?,?,?,?)", (category["id"], category["name"], category["description"], category["description_en"], category["wide"], index * 10))
                    for order, item in enumerate(category["products"]):
                        db().execute("INSERT INTO products (category_id,name,description,description_en,link_type,url,sort_order,published) VALUES (?,?,?,?,?,?,?,1)", (category["id"], item["name"], item["description"], item["description_en"], "url", item["url"], order * 10))
                db().execute("INSERT INTO catalog_migrations VALUES ('initial')")
        if 'series' not in {row['name'] for row in db().execute('PRAGMA table_info(products)')}:
            with db():
                db().execute("ALTER TABLE products ADD COLUMN series TEXT NOT NULL DEFAULT ''")
                for branch in AXIS_SERIES:
                    db().execute('UPDATE products SET series=? WHERE category_id IN (SELECT id FROM product_categories WHERE name=?) AND UPPER(name) LIKE ?', (branch['code'], AXIS, branch['code'] + '%'))
        columns = {row['name'] for row in db().execute('PRAGMA table_info(products)')}
        with db():
            for field in ('rated_torque', 'peak_torque'):
                if field not in columns:
                    db().execute(f"ALTER TABLE products ADD COLUMN {field} TEXT NOT NULL DEFAULT ''")

    def categories():
        return db().execute("SELECT * FROM product_categories ORDER BY sort_order,id").fetchall()

    def product(product_id):
        item = db().execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
        if not item:
            abort(404, description="这个产品不存在或已删除。")
        return item

    def destination(item):
        if item["link_type"] == "url":
            return item["url"]
        if item["link_type"] == "pdf" and item["document_id"] and item["document_published"]:
            return "/document.html?id=" + str(item["document_id"])
        return None

    @catalog.get("/admin/products")
    def products():
        items = db().execute("""SELECT p.*,c.name AS category_name,d.title AS document_title,d.published AS document_published
            FROM products p JOIN product_categories c ON p.category_id=c.id
            LEFT JOIN documents d ON p.document_id=d.id ORDER BY c.sort_order,c.id,p.sort_order,p.id""").fetchall()
        return render_template("products.html", products=items)

    @catalog.route("/admin/products/new", methods=["GET", "POST"])
    @catalog.route("/admin/products/<int:product_id>/edit", methods=["GET", "POST"])
    def edit_product(product_id=None):
        item = product(product_id) if product_id is not None else None
        groups = categories()
        documents = db().execute("SELECT id,title,published FROM documents WHERE source_type='pdf' ORDER BY id DESC").fetchall()
        values = dict(item) if item else {"name": "", "description": "", "description_en": "", "category_id": groups[0]["id"], "sort_order": 0, "link_type": "url", "url": "", "document_id": None}
        values.setdefault('series', 'JP')
        values.setdefault('rated_torque', '')
        values.setdefault('peak_torque', '')
        error = None
        if request.method == "POST":
            values.update({key: request.form.get(key, "").strip() for key in ("name", "description", "description_en", "category_id", "sort_order", "link_type", "url", "document_id", "series", "rated_torque", "peak_torque")})
            try:
                if not 1 <= len(values["name"]) <= 120:
                    raise ValueError("产品名称需要 1 至 120 个字符。")
                if len(values["description"]) > 240 or len(values["description_en"]) > 240:
                    raise ValueError("产品简介最多 240 个字符。")
                for field in ('rated_torque', 'peak_torque'):
                    value = values[field]
                    if value and (len(value) > 12 or not re.fullmatch(r'[0-9]+(?:\.[0-9]+)?', value)):
                        raise ValueError('扭矩请填写不超过 12 个字符的非负数字，单位为 N·m；不填写的参数不会显示。')
                try:
                    category_id = int(values["category_id"])
                    sort_order = int(values["sort_order"])
                except ValueError:
                    raise ValueError("请选择产品分类，并填写有效的排序数字。")
                if category_id not in [category["id"] for category in groups]:
                    raise ValueError("所选分类不存在，请重新选择。")
                axis = next(category for category in groups if category['id'] == category_id)['name'] == AXIS
                series = values['series'] if axis else ''
                if axis and series not in [branch['code'] for branch in AXIS_SERIES]:
                    raise ValueError('请选择 AXIS 产品所属的 JP、JS 或 JC 系列。')
                if not 0 <= sort_order <= 9999:
                    raise ValueError("排序需要填写 0 至 9999 的整数，数字越小越靠前。")
                link_type = values["link_type"]
                if link_type not in ("url", "pdf", "none"):
                    raise ValueError("请选择有效的资料链接方式。")
                url = ""
                document_id = None
                published = int(request.form.get("action") == "publish")
                if link_type == "url":
                    url = values["url"]
                    if not url or len(url) > 2048 or re.search(r"[\x00-\x20\x7f\\]", url):
                        raise ValueError("请填写有效的网页链接地址。")
                    parsed = urlsplit(url)
                    external = parsed.scheme in ("http", "https") and bool(parsed.netloc) and not parsed.username
                    internal = url.startswith("/") and not url.startswith("//") and not parsed.scheme
                    if not (external or internal):
                        raise ValueError("链接需以 https://、http:// 或站内路径 / 开头。")
                elif link_type == "pdf":
                    try:
                        document_id = int(values["document_id"])
                    except ValueError:
                        raise ValueError("请选择一份已上传的 PDF。")
                    linked = db().execute("SELECT published FROM documents WHERE id=? AND source_type='pdf'", (document_id,)).fetchone()
                    if not linked:
                        raise ValueError("所选 PDF 已删除，请重新选择。")
                    if published and not linked["published"]:
                        raise ValueError("请先在资料管理中发布这份 PDF，或将产品保存为草稿。")
                fields = (category_id, values["name"], values["description"], values["description_en"], link_type, url, document_id, sort_order, published, series, values['rated_torque'], values['peak_torque'])
                with db():
                    if item:
                        db().execute("UPDATE products SET category_id=?,name=?,description=?,description_en=?,link_type=?,url=?,document_id=?,sort_order=?,published=?,series=?,rated_torque=?,peak_torque=?,updated_at=CURRENT_TIMESTAMP WHERE id=?", (*fields, product_id))
                    else:
                        db().execute("INSERT INTO products (category_id,name,description,description_en,link_type,url,document_id,sort_order,published,series,rated_torque,peak_torque) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", fields)
                flash("产品已发布，刷新官网即可查看。" if published else "产品草稿已保存。", "success")
                return redirect(url_for("catalog.products"))
            except ValueError as problem:
                error = str(problem)
        return render_template("product_edit.html", product=item, values=values, categories=groups, documents=documents, error=error, axis_series=AXIS_SERIES), 400 if error else 200

    @catalog.post("/admin/products/<int:product_id>/visibility")
    def product_visibility(product_id):
        item = product(product_id)
        if not item["published"] and item["link_type"] == "pdf":
            linked = db().execute("SELECT published FROM documents WHERE id=? AND source_type='pdf'", (item["document_id"],)).fetchone()
            if not linked or not linked["published"]:
                flash("关联 PDF 尚未发布或已删除，请先编辑产品或发布 PDF。", "error")
                return redirect(url_for("catalog.products"))
        with db():
            db().execute("UPDATE products SET published=?,updated_at=CURRENT_TIMESTAMP WHERE id=?", (1 - item["published"], product_id))
        flash("产品已下架。" if item["published"] else "产品已发布。", "success")
        return redirect(url_for("catalog.products"))

    @catalog.post("/admin/products/<int:product_id>/delete")
    def delete_product(product_id):
        product(product_id)
        with db():
            db().execute("DELETE FROM products WHERE id=?", (product_id,))
        flash("产品已删除，关联的 PDF 文档仍会保留。", "success")
        return redirect(url_for("catalog.products"))

    @catalog.get("/api/products")
    def public_products():
        items = db().execute("""SELECT p.*,d.published AS document_published FROM products p
            LEFT JOIN documents d ON p.document_id=d.id WHERE p.published=1 ORDER BY p.sort_order,p.id""").fetchall()
        result = []
        for category in categories():
            group = dict(category)
            group['series'] = []
            if category['name'] == AXIS:
                for branch in AXIS_SERIES:
                    guide = db().execute('SELECT slug FROM guides WHERE category=? AND series=? AND published=1 ORDER BY sort_order,slug LIMIT 1', (AXIS, branch['code'])).fetchone()
                    group['series'].append({**branch, 'guide_href': '/guides.html?doc=' + guide['slug'] if guide else None})
            group["products"] = [{"id": item["id"], "name": item["name"], "series": item['series'], "description": item["description"], "description_en": item["description_en"], "rated_torque": item['rated_torque'], "peak_torque": item['peak_torque'], "href": destination(item), "external": item["link_type"] == "url" and item["url"].startswith(("http://", "https://"))} for item in items if item["category_id"] == category["id"]]
            result.append(group)
        return jsonify(result)

    @catalog.get('/api/axis-series')
    def axis_series():
        return jsonify(AXIS_SERIES)

    app.register_blueprint(catalog)
