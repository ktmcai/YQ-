"""One-time additive import; run using the website venv and PYTHONPATH."""
import argparse
import hashlib
import json
import re
import shutil
import sqlite3
from pathlib import Path
from uuid import uuid4

from pypdf import PdfReader
from guides import GuideHTML, prepare_content, update_asset_references

parser = argparse.ArgumentParser()
parser.add_argument('--data', required=True)
args = parser.parse_args()
folder = Path(__file__).resolve().parent
data = Path(args.data)
slug = 'canopen-ethercat'
marker = 'word-canopen-ethercat-20261110'
validation = json.loads((folder / 'validation.json').read_text(encoding='utf-8'))
raw = (folder / 'content.html').read_text(encoding='utf-8')
pdf = folder / 'YONIQ_AXIS_CANopen_EtherCAT.pdf'
assert hashlib.sha256(raw.encode()).hexdigest() == validation['html_sha256']
assert hashlib.sha256(pdf.read_bytes()).hexdigest() == validation['pdf_sha256']
reader = PdfReader(pdf)
assert not reader.is_encrypted and len(reader.pages) > 0
content, text, resources = prepare_content(raw)
original = GuideHTML()
original.feed(raw)
assert re.sub(r'\s+', '', text) == re.sub(r'\s+', '', ''.join(original.text)), 'Sanitizer changed source text'
assert content.count('<table>') == validation['tables']
assert content.count('<tr>') == validation['rows']
assert len(re.findall(r'<h[23]\b', content)) == validation['headings']
pdf_url = '/guides/canopen-ethercat/assets/YONIQ_AXIS_CANopen_EtherCAT.pdf'
assert resources == {pdf_url}
connection = sqlite3.connect(data / 'documents.sqlite', timeout=30)
connection.execute('PRAGMA foreign_keys=ON')
stored = None
try:
    with connection:
        connection.execute('BEGIN IMMEDIATE')
        if connection.execute('SELECT 1 FROM guide_migrations WHERE name=?', (marker,)).fetchone():
            print('Already imported; no changes.')
        else:
            assert not connection.execute('SELECT 1 FROM guides WHERE slug=?', (slug,)).fetchone(), 'Slug already exists; refusing to overwrite'
            before = connection.execute('SELECT * FROM guides ORDER BY slug').fetchall()
            sort_order = connection.execute("SELECT COALESCE(MAX(sort_order),0)+1 FROM guides WHERE category='协议手册'").fetchone()[0]
            connection.execute('INSERT INTO guides (slug,title,label,category,sort_order,content_html,search_text,published,series) VALUES (?,?,?,?,?,?,?,1,?)',
                               (slug, 'YONIQ AXIS CANopen 与 EtherCAT 用户手册', 'CANopen / EtherCAT 用户手册', '协议手册', sort_order, content, text, ''))
            identifier = uuid4().hex
            stored = data / 'guide-files' / (identifier + '.pdf')
            stored.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(pdf, stored)
            assert hashlib.sha256(stored.read_bytes()).hexdigest() == validation['pdf_sha256']
            connection.execute('INSERT INTO guide_assets (id,guide_slug,public_url,stored_name,original_name,media_type,byte_size) VALUES (?,?,?,?,?,?,?)',
                               (identifier, slug, pdf_url, stored.name, 'YONIQ_AXIS_CANopen_EtherCAT用户手册.pdf', 'application/pdf', stored.stat().st_size))
            update_asset_references(connection, slug, resources)
            assert before == connection.execute('SELECT * FROM guides WHERE slug<>? ORDER BY slug', (slug,)).fetchall(), 'Existing guides changed'
            connection.execute('INSERT INTO guide_migrations (name) VALUES (?)', (marker,))
            print(json.dumps({'slug': slug, 'headings': validation['headings'], 'tables': validation['tables'], 'rows': validation['rows'], 'pdf_pages': len(reader.pages)}, ensure_ascii=False))
except Exception:
    if stored is not None:
        stored.unlink(missing_ok=True)
    raise
finally:
    connection.close()
