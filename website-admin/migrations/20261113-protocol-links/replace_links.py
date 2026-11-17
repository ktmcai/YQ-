"""Replace the three verified device PDF entries; back up the database before running."""
import html
import json
import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from feishu import CANOPEN_MANUAL_FILES, CANOPEN_MANUAL_LINK
from guides import GuideHTML, asset_url, prepare_content, update_asset_references


SLUGS = ('jp57-08', 'jp57-40', 'feishu-1b80d522b2294be5')
PAIRS = re.compile(r'<a\b[^>]*>(?:(?!</a>).)*</a>\s*<a\b[^>]*class="attachment-download"[^>]*>(?:(?!</a>).)*</a>', re.S)


def replace_links(database):
    connection = sqlite3.connect(database, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute('PRAGMA foreign_keys=ON')
    changed = []
    try:
        with connection:
            connection.execute('BEGIN IMMEDIATE')
            assert connection.execute("SELECT 1 FROM guides WHERE slug='canopen-ethercat' AND published=1 AND content_html<>''").fetchone(), 'Target manual is unavailable'
            assert not connection.execute("SELECT 1 FROM guide_sync_jobs WHERE status='running'").fetchone(), 'Wait for active sync'
            replacement = prepare_content(CANOPEN_MANUAL_LINK)[0]
            for slug in SLUGS:
                row = connection.execute('SELECT * FROM guides WHERE slug=? AND published=1', (slug,)).fetchone()
                assert row, slug
                resources = {item['public_url'] for item in connection.execute('SELECT public_url,original_name FROM guide_assets WHERE guide_slug=?', (slug,)) if item['original_name'] in CANOPEN_MANUAL_FILES}
                count = 0

                def replace(match):
                    nonlocal count
                    links = re.findall(r'href="([^"]+)"', match[0])
                    if len(links) != 2 or any(asset_url(html.unescape(link)) not in resources for link in links):
                        return match[0]
                    count += 1
                    return replacement

                content = PAIRS.sub(replace, row['content_html'])
                if count == 0 and replacement in content:
                    continue
                assert count == 1, (slug, count)
                parsed = GuideHTML()
                parsed.feed(content)
                text = re.sub(r'\s+', ' ', ''.join(parsed.text)).strip()
                connection.execute('UPDATE guides SET content_html=?,search_text=?,version=version+1,updated_at=CURRENT_TIMESTAMP WHERE slug=?', (content, text, slug))
                update_asset_references(connection, slug, parsed.assets)
                changed.append({'slug': slug, 'from_version': row['version'], 'to_version': row['version'] + 1})
        return changed
    finally:
        connection.close()


if __name__ == '__main__':
    print(json.dumps(replace_links(sys.argv[1]), ensure_ascii=False))
