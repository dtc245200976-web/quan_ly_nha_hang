import os
import time
import psycopg2
from flask import Flask, redirect, render_template_string, request

app = Flask(__name__)

def get_connection():
    for _ in range(30):
        try:
            return psycopg2.connect(
                host=os.getenv("DB_HOST", "db"),
                dbname=os.getenv("POSTGRES_DB", "restaurant"),
                user=os.getenv("POSTGRES_USER", "restaurant"),
                password=os.getenv("POSTGRES_PASSWORD", "change-this-password"),
            )
        except psycopg2.OperationalError:
            time.sleep(2)
    raise RuntimeError("Cannot connect to database")

def setup_database():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS menu_items (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    price NUMERIC(10, 2) NOT NULL,
                    available BOOLEAN NOT NULL DEFAULT TRUE
                );
                CREATE TABLE IF NOT EXISTS restaurant_tables (
                    id SERIAL PRIMARY KEY,
                    table_number INTEGER NOT NULL UNIQUE,
                    status TEXT NOT NULL DEFAULT 'Available'
                );
                CREATE TABLE IF NOT EXISTS orders (
                    id SERIAL PRIMARY KEY,
                    table_id INTEGER NOT NULL REFERENCES restaurant_tables(id),
                    status TEXT NOT NULL DEFAULT 'Preparing',
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS order_items (
                    id SERIAL PRIMARY KEY,
                    order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
                    menu_item_id INTEGER NOT NULL REFERENCES menu_items(id),
                    quantity INTEGER NOT NULL CHECK (quantity > 0)
                );
                INSERT INTO menu_items (name, price) VALUES
                    ('Pho bo', 50000), ('Com ga', 45000), ('Tra da', 10000)
                    ON CONFLICT (name) DO NOTHING;
                INSERT INTO restaurant_tables (table_number)
                    SELECT n FROM generate_series(1, 10) AS n
                    ON CONFLICT (table_number) DO NOTHING;
            """)

PAGE = """
<!doctype html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Quản lý nhà hàng</title>
<style>
body{font:16px Arial;margin:30px;background:#f5f5f5;color:#222}
main{max-width:1000px;margin:auto}section{background:white;padding:18px;margin:16px 0;border-radius:8px}
input,select,button{padding:9px;margin:4px}button{background:#176b45;color:white;border:0;border-radius:4px}
table{border-collapse:collapse;width:100%}td,th{padding:8px;border-bottom:1px solid #ddd;text-align:left}
</style>
</head>
<body><main>
<h1>Quản lý nhà hàng</h1>
<p>Quản lý thực đơn, bàn và đơn hàng.</p>
<section><h2>Thêm món ăn</h2>
<form method="post" action="/menu/add">
<input name="name" placeholder="Tên món" required>
<input name="price" type="number" min="0" step="1000" placeholder="Giá (VND)" required>
<button>Thêm món</button></form>
<h3>Thực đơn</h3><table><tr><th>Món</th><th>Giá</th></tr>
{% for item in menu %}<tr><td>{{item[1]}}</td><td>{{"{:,.0f}".format(item[2])}} đ</td></tr>{% endfor %}
</table></section>
<section><h2>Tạo đơn hàng</h2>
<form method="post" action="/orders/add">
<label>Bàn <select name="table_id">{% for t in tables %}<option value="{{t[0]}}">Bàn {{t[1]}}</option>{% endfor %}</select></label>
<label>Món <select name="item_id">{% for item in menu %}<option value="{{item[0]}}">{{item[1]}}</option>{% endfor %}</select></label>
<label>Số lượng <input name="quantity" type="number" min="1" value="1" required></label>
<button>Tạo đơn</button></form></section>
<section><h2>Đơn hàng</h2><table>
<tr><th>Mã</th><th>Bàn</th><th>Món</th><th>Số lượng</th><th>Trạng thái</th><th></th></tr>
{% for o in orders %}<tr><td>{{o[0]}}</td><td>Bàn {{o[1]}}</td><td>{{o[2]}}</td><td>{{o[3]}}</td><td>{{o[4]}}</td>
<td>{% if o[4] != 'Completed' %}<form method="post" action="/orders/{{o[0]}}/complete"><button>Hoàn tất</button></form>{% endif %}</td></tr>{% endfor %}
</table></section>
</main></body></html>
"""

@app.get("/")
def home():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, price FROM menu_items WHERE available ORDER BY id")
            menu = cur.fetchall()
            cur.execute("SELECT id, table_number FROM restaurant_tables ORDER BY table_number")
            tables = cur.fetchall()
            cur.execute("""
                SELECT o.id, t.table_number, m.name, oi.quantity, o.status
                FROM orders o
                JOIN restaurant_tables t ON t.id=o.table_id
                JOIN order_items oi ON oi.order_id=o.id
                JOIN menu_items m ON m.id=oi.menu_item_id
                ORDER BY o.id DESC
            """)
            orders = cur.fetchall()
    return render_template_string(PAGE, menu=menu, tables=tables, orders=orders)

@app.post("/menu/add")
def add_menu_item():
    name = request.form["name"].strip()
    price = float(request.form["price"])
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO menu_items (name, price) VALUES (%s, %s) ON CONFLICT (name) DO NOTHING",
                (name, price),
            )
    return redirect("/")

@app.post("/orders/add")
def add_order():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO orders (table_id) VALUES (%s) RETURNING id",
                (request.form["table_id"],),
            )
            order_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO order_items (order_id, menu_item_id, quantity) VALUES (%s, %s, %s)",
                (order_id, request.form["item_id"], request.form["quantity"]),
            )
    return redirect("/")

@app.post("/orders/<int:order_id>/complete")
def complete_order(order_id):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE orders SET status='Completed' WHERE id=%s", (order_id,))
    return redirect("/")

@app.get("/health")
def health():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
    return {"status": "ok", "database": "connected"}

if __name__ == "__main__":
    setup_database()
    app.run(host="0.0.0.0", port=8000)
