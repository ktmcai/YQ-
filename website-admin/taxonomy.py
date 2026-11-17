AXIS = 'YONIQ AXIS'
AXIS_SERIES = [
    {'code': 'JP', 'name': '行星关节执行器', 'name_en': 'Planetary joint actuators'},
    {'code': 'JS', 'name': '应变波关节执行器', 'name_en': 'Strain wave joint actuators'},
    {'code': 'JC', 'name': '摆线关节执行器', 'name_en': 'Cycloidal joint actuators'},
]


def guide_categories(connection):
    names = list(dict.fromkeys(['通用资料'] + [row['category'] for row in connection.execute('SELECT category FROM guides ORDER BY sort_order,slug')]
                               + [row['name'] for row in connection.execute('SELECT name FROM product_categories ORDER BY sort_order,id')]))
    options = {}
    for name in names:
        options[name] = name + ' · 通用文档' if name == AXIS else name
        if name == AXIS:
            for series in AXIS_SERIES:
                options[AXIS + ' / ' + series['code']] = AXIS + ' / ' + series['code'] + ' · ' + series['name']
    return options


def guide_location(value):
    for series in AXIS_SERIES:
        if value == AXIS + ' / ' + series['code']:
            return AXIS, series['code']
    return value, ''
