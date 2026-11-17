import hashlib
import json
import re
import zipfile
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path

folder = Path(__file__).resolve().parent
source = folder.parents[2] / '协议文档' / 'YONIQ_AXIS_CANopen_EtherCAT用户手册.docx'
ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
attr = '{' + ns['w'] + '}'


def compact(value):
    return re.sub(r'\s+', '', value)


class Content(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text, self.headings, self.tables = [], [], []
        self.heading = self.cell = None

    def handle_starttag(self, tag, attrs):
        if tag in ('h2', 'h3'):
            self.heading = []
        if tag == 'table':
            self.tables.append([])
        if tag == 'tr':
            self.tables[-1].append([])
        if tag in ('td', 'th'):
            self.cell = []

    def handle_data(self, data):
        self.text.append(data)
        if self.heading is not None:
            self.heading.append(data)
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag in ('h2', 'h3'):
            self.headings.append(''.join(self.heading))
            self.heading = None
        if tag in ('td', 'th'):
            self.tables[-1][-1].append(compact(''.join(self.cell)))
            self.cell = None


with zipfile.ZipFile(source) as archive:
    root = ET.fromstring(archive.read('word/document.xml'))
    styles = ET.fromstring(archive.read('word/styles.xml'))
    names = {s.get(attr + 'styleId'): s.find('w:name', ns).get(attr + 'val') for s in styles.findall('w:style', ns)}
    expected_text, expected_headings = [], []
    for paragraph in root.findall('.//w:p', ns):
        style = paragraph.find('w:pPr/w:pStyle', ns)
        name = names.get(style.get(attr + 'val'), '') if style is not None else ''
        text = ''.join(t.text or '' for t in paragraph.findall('.//w:t', ns))
        if name not in ('Title', 'toc 1', 'toc 2'):
            expected_text.append(text)
        if name in ('heading 1', 'heading 2'):
            expected_headings.append(text)
    expected_tables = [
        [[compact(''.join(t.text or '' for t in cell.findall('.//w:t', ns))) for cell in row.findall('w:tc', ns)]
         for row in table.findall('w:tr', ns)] for table in root.findall('.//w:tbl', ns)
    ]

content = Content()
content.feed((folder / 'content.html').read_text(encoding='utf-8'))
assert compact(''.join(content.text)) == compact('在线查看原版 PDF · 下载 PDF' + ''.join(expected_text)), 'Body text mismatch'
assert content.headings == expected_headings, 'Heading mismatch'
assert content.tables == expected_tables, 'Table cell mismatch'
report = {
    'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
    'html_sha256': hashlib.sha256((folder / 'content.html').read_bytes()).hexdigest(),
    'pdf_sha256': hashlib.sha256((folder / 'YONIQ_AXIS_CANopen_EtherCAT.pdf').read_bytes()).hexdigest(),
    'headings': len(content.headings), 'tables': len(content.tables),
    'rows': sum(len(table) for table in content.tables),
    'body_characters': len(compact(''.join(expected_text))),
    'result': 'All body text, headings, and every table cell match the Word source; printed TOC omitted in favor of website outline.',
}
(folder / 'validation.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(report, ensure_ascii=False))
