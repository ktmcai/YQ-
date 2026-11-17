import argparse
import json
import mimetypes
import secrets
import shutil
import sqlite3
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4

from app import create_app
from guides import prepare_content, update_asset_references


def import_guides(source, data):
    source, data = Path(source).resolve(), Path(data).resolve()
    create_app({'SECRET_KEY': secrets.token_hex(32), 'DATA_DIR': str(data)})
    connection = sqlite3.connect(data / 'documents.sqlite')
    connection.execute('PRAGMA foreign_keys=ON')
    copied = []
    try:
        with connection:
            connection.execute('BEGIN IMMEDIATE')
            if connection.execute("SELECT 1 FROM guide_migrations WHERE name='feishu-20261109'").fetchone():
                return 0
            catalog = json.loads((source / 'catalog.json').read_text(encoding='utf-8'))
            for order, item in enumerate(catalog):
                folder = (source / item['slug']).resolve()
                if not folder.is_relative_to(source):
                    raise ValueError('Invalid document folder')
                content, text, resources = prepare_content((folder / 'content.html').read_text(encoding='utf-8'))
                connection.execute('INSERT INTO guides (slug,title,label,category,sort_order,content_html,search_text) VALUES (?,?,?,?,?,?,?)', (item['slug'], item['title'], item['label'], item['category'], order, content, text))
                for file in folder.rglob('*'):
                    if not file.is_file() or file.name == 'content.html':
                        continue
                    if file.is_symlink() or not file.resolve().is_relative_to(folder):
                        raise ValueError('Invalid asset path')
                    identifier = uuid4().hex
                    stored = data / 'guide-files' / (identifier + file.suffix.lower())
                    shutil.copyfile(file, stored)
                    copied.append(stored)
                    resource = quote('/guides/' + item['slug'] + '/' + file.relative_to(folder).as_posix(), safe='/')
                    media_type = mimetypes.guess_type(file.name)[0] or 'application/octet-stream'
                    if not media_type.startswith('image/') and file.suffix.lower() != '.pdf':
                        media_type = 'application/octet-stream'
                    connection.execute('INSERT INTO guide_assets (id,guide_slug,public_url,stored_name,original_name,media_type,byte_size) VALUES (?,?,?,?,?,?,?)', (identifier, item['slug'], resource, stored.name, file.name, media_type, file.stat().st_size))
            for item in catalog:
                _, _, resources = prepare_content(connection.execute('SELECT content_html FROM guides WHERE slug=?', (item['slug'],)).fetchone()[0])
                update_asset_references(connection, item['slug'], resources)
            connection.execute("INSERT INTO guide_migrations VALUES ('feishu-20261109')")
        return len(catalog)
    except Exception:
        for file in copied:
            file.unlink(missing_ok=True)
        raise
    finally:
        connection.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True)
    parser.add_argument('--data', required=True)
    args = parser.parse_args()
    print(f'Imported {import_guides(args.source, args.data)} online documents; existing imports are not overwritten.')
