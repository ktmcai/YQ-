import html
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict, deque
from html.parser import HTMLParser
from pathlib import Path


SOURCES = json.loads(Path(__file__).with_name('feishu_sources.json').read_text(encoding='utf-8'))
CANOPEN_MANUAL_FILES = {'YONIQ_AXIS_CANopen_EtherCAT用户手册.pdf', 'YONIQ_AXIS_CANopen_EtherCAT_User_Manual_V2.pdf'}
CANOPEN_MANUAL_LINK = '<a href="/guides.html?doc=canopen-ethercat">CANopen / EtherCAT 用户手册</a>'
# Feishu document color enums, using the public reader's light-theme tokens.
TEXT_COLORS = dict(enumerate(['#d83931', '#de7802', '#dc9b04', '#2ea121', '#245bdb', '#6425d0', '#8f959e'], 1))
BACKGROUND_COLORS = dict(enumerate([
    '#fbbfbc', 'rgba(254,212,164,0.8)', 'rgba(255,246,122,0.8)', 'rgba(183,237,177,0.8)',
    'rgba(186,206,253,0.7)', 'rgba(205,178,250,0.7)', 'rgba(222,224,227,0.8)',
    '#f76964', '#ffa53d', '#ffe928', '#62d256', 'rgba(78,131,253,0.55)',
    'rgba(147,90,246,0.55)', '#bbbfc4', '#f2f3f5',
], 1))
LEGACY_SECTIONS = {
    'LJD0dl9Wqo3EZ6x5TCAchc9BnVg': '电机状态1', 'A4DNdaOoSoeqDCxn2YVcEQxznvF': '电机状态2',
    'ItZ0ddMShoAkZExrt3vcChZDn3r': '电机状态3', 'Cp3WddHDHoXdhZx5DeYcAwupnBd': '电机状态4',
    'GcNHdbMLjo0JdSx7dQIcahQHnYg': '电机执行结果ACK', 'DjZfdkDuZo5UoVxjFZZcd0C5nDP': '电机 MAVLIN_ID信息',
    'ELG1ddRkdoBDRsxcuJ2ckiwfnGd': '电机 CAN ID 信息', 'N8NldQTjEoQfYdxfkyRce4APncf': '电机控制参数表',
    'VotUdOELdo5K3zx8WkbcVVOknfb': '电机保护参数表', 'QyMwdAKsGoBmQcxwBafct71Rn4f': '电机限制参数表',
}


class SyncError(Exception):
    pass


def document_url(value):
    value = value.strip()
    try:
        parsed = urllib.parse.urlsplit(value)
        if (len(value) > 2048 or re.search(r'[\s\\\x00-\x1f\x7f]', value)
                or parsed.scheme != 'https' or parsed.username or parsed.password or parsed.port
                or not re.fullmatch(r'(?:[a-z0-9-]+\.)+feishu\.cn', parsed.hostname or '')
                or not re.fullmatch(r'/(?:docx|wiki)/[A-Za-z0-9]{1,128}/?', parsed.path)):
            raise ValueError
    except ValueError:
        raise SyncError('请粘贴完整的飞书文档链接（https://…feishu.cn/docx/… 或 /wiki/…）。') from None
    return 'https://' + parsed.hostname + parsed.path.rstrip('/')


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise SyncError('飞书返回了意外的下载跳转，本次未发布。')


class FeishuClient:
    def __init__(self, app_id, secret):
        self.opener = urllib.request.build_opener(NoRedirect())
        self.token = None
        self.next_request = 0
        self.sheet_revisions = {}
        result = self.json('/auth/v3/tenant_access_token/internal', {'app_id': app_id, 'app_secret': secret})
        self.token = result['tenant_access_token']

    def request(self, path, data=None):
        time.sleep(max(0, self.next_request - time.monotonic()))
        self.next_request = time.monotonic() + .23
        headers = {'Content-Type': 'application/json'}
        if self.token:
            headers['Authorization'] = 'Bearer ' + self.token
        request = urllib.request.Request('https://open.feishu.cn/open-apis' + path,
                                         data=json.dumps(data).encode() if data is not None else None, headers=headers)
        for attempt in range(3):
            try:
                return self.opener.open(request, timeout=35)
            except urllib.error.HTTPError as error:
                if error.code in (429, 500, 502, 503, 504) and attempt < 2:
                    error.close()
                    time.sleep(2 ** attempt)
                    continue
                status = error.code
                if path.startswith('/sheet_ai/') and status in (400, 403):
                    try:
                        problem = json.loads(error.read(65536))
                    except (ValueError, OSError):
                        problem = {}
                    if problem.get('code') == 99991672:
                        error.close()
                        raise SyncError('读取表格颜色需要应用身份权限 sheets:spreadsheet:read，请在飞书应用后台开通并发布版本后重试。') from None
                error.close()
                if status == 403:
                    raise SyncError('无法读取这份飞书资料。请在原文档右上角“…”→“添加文档应用”中，将“YONIQ 官网文档同步”设为“可阅读”，然后重试。') from None
                raise SyncError(f'飞书接口返回 HTTP {status}，请检查应用权限或稍后重试。') from None
            except (urllib.error.URLError, TimeoutError):
                raise SyncError('连接飞书超时或网络异常，请稍后重试。') from None

    def json(self, path, data=None):
        with self.request(path, data) as response:
            raw = response.read(16 * 1024 * 1024 + 1)
        if len(raw) > 16 * 1024 * 1024:
            raise SyncError('飞书返回内容过大，本次未发布。')
        result = json.loads(raw)
        if result.get('code') != 0:
            raise SyncError(f'飞书接口错误 {result.get("code")}，请检查文档授权或稍后重试。')
        return result.get('data', result)

    def metadata(self, document_id):
        return self.json('/docx/v1/documents/' + document_id)['document']

    def resolve(self, url):
        token = url.rsplit('/', 1)[-1]
        if '/wiki/' in url:
            node = self.json('/wiki/v2/spaces/get_node?token=' + token)['node']
            if node['obj_type'] != 'docx':
                raise SyncError('这个知识库链接不是文档，请使用文档页面链接。')
            token = node['obj_token']
        return token

    def document(self, source):
        token = self.resolve(source['url'])
        if token != source['document_id']:
            raise SyncError('飞书来源指向了另一份文档，请先核对来源绑定。')
        meta = self.metadata(token)
        blocks, cursor, cursors = [], '', set()
        while True:
            # Tenant tokens can read the latest revision only; verify it again before publishing.
            query = urllib.parse.urlencode({'page_size': 500, **({'page_token': cursor} if cursor else {})})
            page = self.json('/docx/v1/documents/' + token + '/blocks?' + query)
            blocks.extend(page['items'])
            if len(blocks) > 20000:
                raise SyncError('文档超过 20000 个内容块，本次未发布。')
            if not page.get('has_more'):
                break
            cursor = page.get('page_token')
            if not cursor or cursor in cursors:
                raise SyncError('飞书正文分页不完整，本次未发布。')
            cursors.add(cursor)
        return meta, blocks

    def inline(self, document_id, block_id):
        return self.json(f'/docx/v1/documents/{document_id}/blocks/{block_id}')['block']

    def sheet(self, token):
        workbook, sheet_id = token.rsplit('_', 1)
        meta = self.json('/sheets/v2/spreadsheets/' + workbook + '/metainfo')
        sheet = next((s for s in meta['sheets'] if s['sheetId'] == sheet_id), None)
        if not sheet or sheet['rowCount'] > 2000 or sheet['columnCount'] > 100:
            raise SyncError('嵌入表格不存在或超过 2000 行 / 100 列，本次未发布。')
        letters = column_name(sheet['columnCount'])
        result = self.json(f'/sheets/v2/spreadsheets/{workbook}/values/{sheet_id}!A1:{letters}{sheet["rowCount"]}?valueRenderOption=ToString&dateTimeRenderOption=FormattedString')
        revision = meta['properties']['revision']
        if result['revision'] != revision or self.sheet_revisions.get(workbook, revision) != revision:
            raise SyncError('飞书表格正在修改，请编辑完成后重新同步。')
        self.sheet_revisions[workbook] = revision
        sheet['cell_styles'] = self.sheet_styles(workbook, sheet_id, sheet['rowCount'], sheet['columnCount'])
        layout = self.json('/sheet_ai/v2/spreadsheets/' + workbook + '/tools/invoke_read', {
            'tool_name': 'get_sheet_structure', 'input': json.dumps({
                'excel_id': workbook, 'sheet_id': sheet_id, 'range': f'A1:{letters}{sheet["rowCount"]}',
                'info_type': 'row_heights_column_widths'})})
        layout = json.loads(layout['output'])
        if layout.get('revision') != revision:
            raise SyncError('飞书表格尺寸在读取期间发生修改，请重新同步。')
        sheet['column_widths'] = sheet_dimensions(layout.get('column_widths', []), 'cols', 'width', sheet['columnCount'])
        sheet['row_heights'] = sheet_dimensions(layout.get('row_heights', []), 'rows', 'height', sheet['rowCount'])
        return sheet, result['valueRange']['values']

    def sheet_styles(self, workbook, sheet_id, rows, columns):
        styles = {}
        column_names = [column_name(col) for col in range(1, columns + 1)]
        for start in range(1, rows + 1, 100):
            end = min(start + 99, rows)
            area = f'A{start}:{column_names[-1]}{end}'
            payload = {'excel_id': workbook, 'sheet_id': sheet_id, 'ranges': [area],
                       'include_styles': True, 'include_conditional_format_style': True,
                       'cell_limit': 10000, 'max_chars': 8000000}
            result = self.json('/sheet_ai/v2/spreadsheets/' + workbook + '/tools/invoke_read',
                               {'tool_name': 'get_cell_ranges', 'input': json.dumps(payload)})
            result = json.loads(result['output'])
            # Never publish a partially styled table or infer coordinates from array offsets.
            if result.get('has_more') or result.get('truncated') or len(result.get('ranges', [])) != 1:
                raise SyncError('飞书表格样式读取不完整，本次未发布。')
            region = result['ranges'][0]
            if (region.get('has_more') or region.get('truncated') or region.get('actual_range') != area
                    or region.get('row_indices') != list(range(start, end + 1))
                    or region.get('col_indices') != column_names
                    or len(region.get('cells', [])) != end - start + 1):
                raise SyncError('飞书表格样式范围不完整，本次未发布。')
            for row, cells in zip(region['row_indices'], region['cells']):
                if len(cells) != columns or any('cell_styles' not in cell for cell in cells):
                    raise SyncError('飞书表格单元格样式缺失，本次未发布。')
                for col, cell in enumerate(cells):
                    styles[row - 1, col] = sheet_cell_style(cell['cell_styles'])
        return styles

    def verify_revision(self, meta):
        if self.metadata(meta['document_id'])['revision_id'] != meta['revision_id']:
            raise SyncError('飞书文档在同步期间发生修改，请重新同步。')
        for token, revision in self.sheet_revisions.items():
            if self.json('/sheets/v2/spreadsheets/' + token + '/metainfo')['properties']['revision'] != revision:
                raise SyncError('飞书表格在同步期间发生修改，请重新同步。')

    def download(self, token, destination, board=False):
        path = f'/board/v1/whiteboards/{token}/download_as_image' if board else f'/drive/v1/medias/{token}/download'
        with self.request(path) as response, destination.open('wb') as output:
            expected = response.headers.get('Content-Length')
            size = 0
            while chunk := response.read(65536):
                size += len(chunk)
                if size > 150 * 1024 * 1024:
                    raise SyncError('单个附件超过 150 MB，本次未发布。')
                output.write(chunk)
        if not size or (expected and size != int(expected)):
            raise SyncError('图片或附件下载不完整，本次未发布。')


def normalize_heading(value):
    return re.sub(r'\s+', '', re.sub(r'^\d+(?:\.\d+)*[.、\s]+', '', value)).casefold()


def fill_protocol_placeholders(content):
    headings = list(re.finditer(r'<h([2-6])\b[^>]*>(.*?)</h\1>', content, re.S))
    parent_level = None
    additions = []
    for index, heading in enumerate(headings):
        level = int(heading[1])
        title = normalize_heading(html.unescape(re.sub(r'<[^>]+>', '', heading[2])))
        if parent_level is not None and level <= parent_level:
            parent_level = None
        if title == '协议手册':
            parent_level = level
            continue
        if parent_level is None:
            continue
        if title in ('canopen协议', 'ethercat协议', 'canopen/ethercat协议', 'canopen／ethercat协议'):
            link = CANOPEN_MANUAL_LINK
        elif title == '串口协议':
            link = '<a href="/guides.html?doc=serial-protocol">串口协议手册</a>'
        else:
            continue
        end = next((item.start() for item in headings[index + 1:] if int(item[1]) <= level), len(content))
        # Only fill blank sections; links, images, tables and explanatory text are content.
        if re.fullmatch(r'(?:\s|&nbsp;|<br>|</?(?:p|span|strong|b|em|i|u|s)(?:\s[^>]*)?>)*', content[heading.end():end]):
            additions.append((heading.end(), '<p>' + link + '</p>'))
    for position, link in reversed(additions):
        content = content[:position] + link + content[position:]
    return content


class HeadingMap(HTMLParser):
    def __init__(self, content):
        super().__init__()
        self.items = defaultdict(deque)
        self.current = None
        self.feed(content)

    def handle_starttag(self, tag, attrs):
        if tag in ('h2', 'h3', 'h4', 'h5', 'h6'):
            self.current = [dict(attrs).get('id'), '']

    def handle_data(self, data):
        if self.current:
            self.current[1] += data

    def handle_endtag(self, tag):
        if self.current and tag in ('h2', 'h3', 'h4', 'h5', 'h6'):
            identifier, text = self.current
            if identifier:
                self.items[normalize_heading(text)].append(identifier)
            self.current = None


def column_name(column):
    letters = ''
    while column:
        column, digit = divmod(column - 1, 26)
        letters = chr(65 + digit) + letters
    return letters


def sheet_cell_style(style):
    rules = []
    family = style.get('font_family')
    if isinstance(family, str) and re.fullmatch(r'[\w .-]{1,100}', family):
        # Feishu resolves the Chinese Song font to SimSun and uses serif fallbacks.
        family = 'SimSun,"宋体","Songti SC",STSong,serif' if family == '宋体' else '"' + family + '",sans-serif'
        rules.append('font-family:' + family)
    size = style.get('font_size')
    if type(size) in (int, float) and 1 <= size <= 300:
        # Sheets sizes are points; its canvas renderer truncates the 96/72 conversion.
        rules.append(f'font-size:{int(size * 4 / 3)}px')
    for key, css in [('font_color', 'color'), ('background_color', 'background-color')]:
        value = style.get(key, '')
        if not isinstance(value, str):
            continue
        rgb = re.fullmatch(r'rgb\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*\)', value)
        rgba = re.fullmatch(r'rgba\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(0(?:\.\d+)?|1(?:\.0+)?)\s*\)', value)
        if (re.fullmatch(r'#[0-9a-fA-F]{6}', value)
                or (rgb and all(int(n) <= 255 for n in rgb.groups()))
                or (rgba and all(int(n) <= 255 for n in rgba.groups()[:3]))):
            rules.append(css + ':' + value)
    for key, css, allowed in [
        ('font_weight', 'font-weight', ('normal', 'bold')),
        ('font_style', 'font-style', ('normal', 'italic')),
        ('font_line', 'text-decoration', ('none', 'underline', 'line-through')),
        ('horizontal_alignment', 'text-align', ('left', 'center', 'right')),
        ('vertical_alignment', 'vertical-align', ('top', 'middle', 'bottom')),
    ]:
        if style.get(key) in allowed:
            rules.append(css + ':' + style[key])
    return ';'.join(rules)


def sheet_dimensions(groups, axis, field, count):
    labels = [column_name(i) if axis == 'cols' else str(i) for i in range(1, count + 1)]
    positions = {label: i for i, label in enumerate(labels)}
    dimensions = [None] * count
    for group in groups:
        bounds = group.get(axis, '').split(':')
        size = group.get(field)
        if (len(bounds) != 2 or any(label not in positions for label in bounds)
                or type(size) not in (int, float) or not 0 < size <= 10000):
            raise SyncError('飞书表格行高或列宽无效，本次未发布。')
        start, end = (positions[label] for label in bounds)
        if start > end or any(value is not None for value in dimensions[start:end + 1]):
            raise SyncError('飞书表格尺寸范围重叠或顺序无效，本次未发布。')
        dimensions[start:end + 1] = [size] * (end - start + 1)
    if any(value is None for value in dimensions):
        raise SyncError('飞书表格行高或列宽缺失，本次未发布。')
    return dimensions


def table_html(rows, columns, cells, merges, styles=None, widths=None, heights=None):
    if rows < 1 or columns < 1 or rows * columns > 200000:
        raise SyncError('表格尺寸无效，本次未发布。')
    for sizes, count in ((widths, columns), (heights, rows)):
        if sizes is not None and (len(sizes) != count or any(type(s) not in (int, float) or not 0 < s <= 10000 for s in sizes)):
            raise SyncError('飞书表格尺寸无效，本次未发布。')
    spans, covered = {}, set()
    for row, col, height, width in merges:
        if min(row, col) < 0 or min(height, width) < 1 or row + height > rows or col + width > columns:
            raise SyncError('表格合并范围无效，本次未发布。')
        if (row, col) in covered:
            raise SyncError('表格合并范围重叠，本次未发布。')
        spans[row, col] = (height, width)
        for r in range(row, row + height):
            for c in range(col, col + width):
                if (r, c) != (row, col):
                    covered.add((r, c))
    output = ['<div class="table-scroll" tabindex="0" role="region" aria-label="数据表格">']
    if widths is not None:
        classes = 'feishu-table feishu-sheet' if heights is not None else 'feishu-table'
        output.append(f'<table class="{classes}" style="width:{sum(widths):g}px"><colgroup>')
        output.extend(f'<col style="width:{width:g}px">' for width in widths)
        output.append('</colgroup><tbody>')
    else:
        output.append('<table><tbody>')
    for row in range(rows):
        output.append(f'<tr style="height:{heights[row]:g}px">' if heights is not None else '<tr>')
        for col in range(columns):
            if (row, col) in covered:
                continue
            height, width = spans.get((row, col), (1, 1))
            attributes = (f' rowspan="{height}"' if height > 1 else '') + (f' colspan="{width}"' if width > 1 else '')
            if styles and styles.get((row, col)):
                attributes += ' style="' + html.escape(styles[row, col], quote=True) + '"'
            output.append(f'<td{attributes}>{cells[row][col]}</td>')
        output.append('</tr>')
    return ''.join(output) + '</tbody></table></div>'


class Renderer:
    def __init__(self, client, meta, blocks, asset, old_html, slug, sources=None):
        self.client, self.meta, self.asset, self.slug = client, meta, asset, slug
        self.sources = SOURCES if sources is None else sources
        self.blocks = {b['block_id']: b for b in blocks}
        if len(self.blocks) != len(blocks):
            raise SyncError('飞书返回重复内容块，本次未发布。')
        self.visited = set()
        self.anchors, self.titles = {}, {}
        previous = HeadingMap(old_html).items
        for block in blocks:
            if 3 <= block['block_type'] <= 11:
                text = ''.join(e.get('text_run', {}).get('content', '') for e in block['heading' + str(block['block_type'] - 2)]['elements'])
                if text.strip():
                    key = normalize_heading(text)
                    self.anchors[block['block_id']] = previous[key].popleft() if previous[key] else 'section-' + block['block_id']
                    self.titles.setdefault(key, self.anchors[block['block_id']])
        self.stats = {'images': 0, 'files': 0, 'tables': 0, 'boards': 0, 'headings': len(self.anchors)}

    def link(self, value):
        value = urllib.parse.unquote(value) if value.lower().startswith(('https%3a', 'http%3a')) else value
        parsed = urllib.parse.urlsplit(value)
        if not parsed.hostname or not parsed.hostname.endswith('.feishu.cn'):
            return value
        token = parsed.path.rstrip('/').rsplit('/', 1)[-1]
        fragment = parsed.fragment.removeprefix('share-')
        if token == 'FwE7w2rONiH1RrkPrmHcXLnVnDg' and self.slug == 'serial-protocol':
            anchor = self.titles.get(normalize_heading(LEGACY_SECTIONS.get(fragment, '')))
            if not anchor:
                raise SyncError('协议手册引用的旧章节无法匹配，本次未发布。')
            return '#' + anchor
        for slug, source in self.sources.items():
            if slug != self.slug and not source.get('published', 1):
                continue
            if token in (source['document_id'], source['url'].rsplit('/', 1)[-1]):
                anchor = self.anchors.get(fragment) if slug == self.slug else None
                return '/guides.html?doc=' + slug + ('#' + anchor if anchor else '')
        return value

    def rich(self, elements, code=False):
        output = []
        for element in elements:
            if 'text_run' in element:
                item = element['text_run']
                text = html.escape(item['content'])
            elif 'mention_doc' in element:
                item = element['mention_doc']
                text = f'<a href="{html.escape(self.link(item["url"]), quote=True)}">{html.escape(item["title"])}</a>'
            elif 'inline_block' in element:
                identifier = element['inline_block']['block_id']
                if identifier not in self.blocks:
                    self.blocks[identifier] = self.client.inline(self.meta['document_id'], identifier)
                output.append(self.block(identifier))
                continue
            else:
                raise SyncError('文档包含暂不支持的行内内容，本次未发布。')
            if not code:
                text = text.replace('\n', '<br>')
                style = item.get('text_element_style', {})
                for key, tag in [('bold', 'strong'), ('italic', 'em'), ('underline', 'u'), ('strikethrough', 's'), ('inline_code', 'code')]:
                    if style.get(key):
                        text = f'<{tag}>{text}</{tag}>'
                colors = []
                for key, css, palette in [('text_color', 'color', TEXT_COLORS), ('background_color', 'background-color', BACKGROUND_COLORS)]:
                    if style.get(key) in palette:
                        colors.append(css + ':' + palette[style[key]])
                if colors:
                    text = '<span style="' + ';'.join(colors) + '">' + text + '</span>'
                if style.get('link', {}).get('url'):
                    text = f'<a href="{html.escape(self.link(style["link"]["url"]), quote=True)}">{text}</a>'
            output.append(text)
        return ''.join(output)

    def children(self, block):
        output, listing = [], None
        inline = {e['inline_block']['block_id'] for value in block.values() if isinstance(value, dict)
                  for e in value.get('elements', []) if 'inline_block' in e}
        for identifier in block.get('children', []):
            if identifier in inline:
                continue
            child = self.blocks.get(identifier)
            if child is None:
                raise SyncError('飞书正文缺少子内容块，本次未发布。')
            kind = {12: 'ul', 13: 'ol'}.get(child['block_type'])
            if kind != listing:
                if listing:
                    output.append(f'</{listing}>')
                if kind:
                    sequence = child.get('ordered', {}).get('style', {}).get('sequence', '1')
                    start = f' start="{int(sequence)}"' if kind == 'ol' and str(sequence).isdigit() else ''
                    output.append(f'<{kind}{start}>')
                listing = kind
            output.append(self.block(identifier))
        if listing:
            output.append(f'</{listing}>')
        return ''.join(output)

    def block(self, identifier):
        if identifier in self.visited:
            raise SyncError('飞书内容块重复引用或存在循环，本次未发布。')
        self.visited.add(identifier)
        block = self.blocks[identifier]
        kind = block['block_type']
        if kind in (1, 32, 33):
            return self.children(block)
        if kind == 24:
            content = self.children(block)
            return '<div class="feishu-columns">' + content + '</div>' if content else ''
        if kind == 25:
            width = block['grid_column']['width_ratio']
            if type(width) not in (int, float) or not 0 < width <= 100:
                raise SyncError('飞书分栏宽度无效，本次未发布。')
            content = self.children(block)
            return f'<div class="feishu-column" style="width:{width:g}%">' + content + '</div>' if content else ''
        if kind in (2, 12, 13, 14) or 3 <= kind <= 11:
            field = {2: 'text', 12: 'bullet', 13: 'ordered', 14: 'code'}.get(kind, 'heading' + str(kind - 2))
            text = self.rich(block[field]['elements'], kind == 14)
            if kind == 14:
                return '<pre><code>' + text + '</code></pre>'
            child_html = self.children(block)
            if 3 <= kind <= 11:
                if identifier not in self.anchors:
                    return child_html
                tag = 'h' + str(min(6, kind - 1))
                return f'<{tag} id="{self.anchors[identifier]}">{text}</{tag}>' + child_html
            tag = 'li' if kind in (12, 13) else 'p'
            align = {2: 'center', 3: 'right'}.get(block[field].get('style', {}).get('align'))
            style = f' style="text-align:{align}"' if align else ''
            if tag == 'li':
                return f'<li{style}>{text}{child_html}</li>'
            return (f'<p{style}>{text}</p>' if text else '') + child_html
        if kind == 19:
            return '<blockquote>' + self.children(block) + '</blockquote>'
        if kind in (23, 27, 43):
            item = block[{23: 'file', 27: 'image', 43: 'board'}[kind]]
            name = item.get('name', '画板.jpg' if kind == 43 else '图片')
            if kind == 23 and name in CANOPEN_MANUAL_FILES and self.slug != 'canopen-ethercat':
                return CANOPEN_MANUAL_LINK
            if kind == 23 and name == '串口协议手册.pdf' and self.slug != 'serial-protocol':
                # Keep the existing online entry regardless of its position in the source.
                for source in self.blocks.values():
                    for value in source.values():
                        for element in value.get('elements', []) if isinstance(value, dict) else []:
                            url = (element.get('mention_doc', {}).get('url', '') or
                                   element.get('text_run', {}).get('text_element_style', {}).get('link', {}).get('url', ''))
                            if self.link(url) == '/guides.html?doc=serial-protocol':
                                return ''
                return '<a href="/guides.html?doc=serial-protocol">串口协议手册</a>'
            resource, width, height = self.asset(item['token'], name, kind != 23, kind == 43)
            self.stats[{23: 'files', 27: 'images', 43: 'boards'}[kind]] += 1
            if kind != 23:
                return f'<img src="{resource}" alt="{html.escape(name)}" width="{width}" height="{height}" loading="lazy" decoding="async">'
            if name.lower().endswith('.pdf'):
                viewer = '/vendor/pdfjs-6.4.299-legacy/web/viewer.html?file=' + urllib.parse.quote(resource, safe='') + '#zoom=page-fit'
                return f'<a href="{viewer}">{html.escape(name)}</a> <a class="attachment-download" href="{resource}" download>下载 PDF</a>'
            return f'<a href="{resource}" download>{html.escape(name)}</a>'
        if kind == 30:
            info, values = self.client.sheet(block['sheet']['token'])
            rows, columns = info['rowCount'], info['columnCount']
            cells = []
            for row in range(rows):
                line = values[row] if row < len(values) else []
                if any(isinstance(v, (dict, list)) for v in line):
                    raise SyncError('嵌入表格包含暂不支持的图片或复杂单元格，本次未发布。')
                cells.append([html.escape(str(line[col])).replace('\n', '<br>') if col < len(line) and line[col] is not None else '' for col in range(columns)])
            merges = [(m['startRowIndex'], m['startColumnIndex'], m['rowCount'], m['columnCount']) for m in info.get('merges', [])]
            self.stats['tables'] += 1
            return table_html(rows, columns, cells, merges, info['cell_styles'], info['column_widths'], info['row_heights'])
        if kind == 31:
            table = block['table']; props = table['property']
            rows, columns = props['row_size'], props['column_size']
            if len(table['cells']) != rows * columns:
                raise SyncError('飞书表格单元格不完整，本次未发布。')
            cells = [[self.block(table['cells'][row * columns + col]) for col in range(columns)] for row in range(rows)]
            merges = [(i // columns, i % columns, m['row_span'], m['col_span']) for i, m in enumerate(props.get('merge_info', [])) if m['row_span'] > 1 or m['col_span'] > 1]
            self.stats['tables'] += 1
            return table_html(rows, columns, cells, merges, widths=props.get('column_width'))
        raise SyncError(f'文档包含暂不支持的内容类型（{kind}），本次未发布，请联系维护人员适配。')

    def render(self):
        content = self.block(self.meta['document_id'])
        if self.visited != set(self.blocks):
            raise SyncError('文档部分内容未能转换，本次未发布。')
        if not content.strip():
            raise SyncError('飞书文档正文为空，本次未发布。')
        if self.slug not in ('canopen-ethercat', 'serial-protocol'):
            content = fill_protocol_placeholders(content)
        return '<div class="feishu-document">' + content + '</div>'
