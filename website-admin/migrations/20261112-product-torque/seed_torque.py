"""One-time torque values verified against the public selection guide on 2026-11-12.

Source: https://yoniqtech.com/guides.html?doc=selection
Run after products.py has added the two torque columns; pass the SQLite path.
Existing administrator-entered values are preserved.
"""
import sqlite3
import sys


VALUES = {
    'JP57-08 G1': ('2.5', '6'),
    'JP57-40 G1': ('7.5', '27'),
    'JP76-48 G1': ('30', '97'),
}
MARKER = 'product-torque-20261112'


def seed(database):
    connection = sqlite3.connect(database)
    try:
        with connection:
            if connection.execute('SELECT 1 FROM catalog_migrations WHERE name=?', (MARKER,)).fetchone():
                return
            for name, (rated, peak) in VALUES.items():
                rows = connection.execute(
                    'SELECT p.id FROM products p JOIN product_categories c ON c.id=p.category_id '
                    'WHERE p.name=? AND c.name=?', (name, 'YONIQ AXIS')
                ).fetchall()
                if len(rows) != 1:
                    raise ValueError(f'Expected exactly one AXIS product: {name}')
                connection.execute(
                    "UPDATE products SET rated_torque=CASE WHEN rated_torque='' THEN ? ELSE rated_torque END, "
                    "peak_torque=CASE WHEN peak_torque='' THEN ? ELSE peak_torque END WHERE id=?",
                    (rated, peak, rows[0][0]),
                )
            connection.execute('INSERT INTO catalog_migrations (name) VALUES (?)', (MARKER,))
    finally:
        connection.close()


if __name__ == '__main__':
    seed(sys.argv[1])
