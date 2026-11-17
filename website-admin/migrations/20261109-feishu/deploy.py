import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys

stage = Path(sys.argv[1]).resolve()
site = Path('/var/www/yoniq')
payload = stage / 'site'
manifest = json.loads((stage / 'manifest.json').read_text())
sources = json.loads((stage / 'sources.json').read_text(encoding='utf-8-sig'))
changes = [item for item in sources if item.get('productId')]
assert len(changes) == 7
for name, expected in manifest.items():
    candidate = (payload / name).resolve()
    assert candidate.is_relative_to(payload.resolve())
    assert hashlib.sha256(candidate.read_bytes()).hexdigest() == expected, name
for name in ('guides', 'guides.html', 'guides.css', 'guides.js'):
    if (site / name).exists():
        raise RuntimeError('New documentation path already exists: ' + name)

data = Path('/var/lib/yoniq-docs')
db = sqlite3.connect(data / 'documents.sqlite', timeout=30)
db.row_factory = sqlite3.Row
for item in changes:
    row = db.execute('SELECT * FROM products WHERE id=?', (item['productId'],)).fetchone()
    assert row and row['link_type'] == 'url' and row['url'].split('?')[0] == item['source'], item['slug']
backup = Path('/var/backups/yoniq-docs') / ('before-feishu-migration-' + datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d-%H%M%S'))
backup.mkdir(mode=0o700)
shutil.copytree(site, backup / 'website')
with sqlite3.connect(backup / 'documents.sqlite') as destination:
    db.backup(destination)
shutil.copytree(data / 'files', backup / 'files')
shutil.copy2(stage / 'sources.json', backup / 'sources.json')
shutil.copy2(stage / 'manifest.json', backup / 'manifest.json')
shutil.copytree(payload / 'guides', site / 'guides')
for name in ('guides.html', 'guides.css', 'guides.js'):
    shutil.copy2(payload / name, site / name)
for item in [site / name for name in ('guides.html', 'guides.css', 'guides.js')] + list((site / 'guides').rglob('*')) + [site / 'guides']:
    item.chmod(0o755 if item.is_dir() else 0o644)
for name, expected in manifest.items():
    if name != 'index.html':
        assert hashlib.sha256((site / name).read_bytes()).hexdigest() == expected, name
protected = ('documents', 'admin', 'product_categories', 'catalog_migrations')
try:
    db.execute('BEGIN IMMEDIATE')
    before = {name: [tuple(row) for row in db.execute('SELECT * FROM ' + name + ' ORDER BY rowid')] for name in protected}
    originals = [dict(row) for row in db.execute('SELECT * FROM products ORDER BY id')]
    for item in changes:
        row = db.execute('SELECT url,link_type FROM products WHERE id=?', (item['productId'],)).fetchone()
        assert row['link_type'] == 'url' and row['url'].split('?')[0] == item['source'], item['slug']
        changed = db.execute('UPDATE products SET url=?,updated_at=CURRENT_TIMESTAMP WHERE id=? AND url=?', ('/guides.html?doc=' + item['slug'], item['productId'], row['url']))
        assert changed.rowcount == 1
    after = {name: [tuple(row) for row in db.execute('SELECT * FROM ' + name + ' ORDER BY rowid')] for name in protected}
    assert before == after
    current = [dict(row) for row in db.execute('SELECT * FROM products ORDER BY id')]
    for old, new in zip(originals, current):
        assert {k:v for k,v in old.items() if k not in ('url','updated_at')} == {k:v for k,v in new.items() if k not in ('url','updated_at')}
    shutil.copy2(payload / 'index.html', site / 'index.html.next')
    (site / 'index.html.next').chmod(0o644)
    os.replace(site / 'index.html.next', site / 'index.html')
    db.commit()
except Exception:
    db.rollback()
    shutil.copy2(backup / 'website' / 'index.html', site / 'index.html')
    raise
finally:
    db.close()
for name, expected in manifest.items():
    assert hashlib.sha256((site / name).read_bytes()).hexdigest() == expected, name
print(json.dumps({'backup': str(backup), 'verified_files':len(manifest), 'updated_products': len(changes), 'existing_records_preserved':True}))
