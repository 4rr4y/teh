import sqlite3
from pathlib import Path
from _lib import rng

PROMPT = ("Write top_customers.sql: an SQLite query on shop.db that returns the 5 customers who spent the most in "
          "2025 (quantity times unit price, over all their 2025 orders), with the columns name and total (rounded to "
          "2 decimals), biggest first.")
KIND, SIZE, WEB = "dev", "short", False

def setup(d):
    r, db = rng(71), sqlite3.connect(Path(d, "shop.db"))
    db.executescript("""
        CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT NOT NULL, country TEXT);
        CREATE TABLE orders (id INTEGER PRIMARY KEY, customer_id INTEGER REFERENCES customers(id),
                             ordered_at TEXT NOT NULL, status TEXT NOT NULL);
        CREATE TABLE order_items (order_id INTEGER REFERENCES orders(id), product TEXT, quantity INTEGER,
                                  unit_price REAL);""")
    names = [f"{a} {b}" for a in ("Ana", "Ben", "Chen", "Dara", "Eli", "Fay", "Gus", "Hana") for b in
             ("Ng", "Ito", "Kaur", "Moss", "Reyes", "Vu", "Weber")]
    db.executemany("INSERT INTO customers VALUES (?, ?, ?)",
                   [(i, n, r.choice(("SG", "MY", "ID", "PH"))) for i, n in enumerate(names, 1)])
    item = 0
    for order in range(1, 801):
        year = r.choice((2024, 2025, 2025))
        db.execute("INSERT INTO orders VALUES (?, ?, ?, ?)", (order, r.randint(1, len(names)),
                   f"{year}-{r.randint(1, 12):02}-{r.randint(1, 28):02}T{r.randint(0, 23):02}:{r.randint(0, 59):02}",
                   r.choice(("paid", "paid", "paid", "shipped"))))
        for _ in range(r.randint(1, 4)):
            item += 1
            db.execute("INSERT INTO order_items VALUES (?, ?, ?, ?)",
                       (order, r.choice(("tea", "kettle", "cups", "tray")), r.randint(1, 6),
                        round(r.uniform(2, 80), 2) + item * 1e-4))  # tiny offsets: no ties
    db.commit()
    db.close()

EXPECTED = """SELECT c.name, ROUND(SUM(i.quantity * i.unit_price), 2) AS total
FROM customers c JOIN orders o ON o.customer_id = c.id JOIN order_items i ON i.order_id = o.id
WHERE o.ordered_at >= '2025-01-01' AND o.ordered_at < '2026-01-01'
GROUP BY c.id ORDER BY SUM(i.quantity * i.unit_price) DESC LIMIT 5"""

def check(d, answer):
    path = Path(d, "top_customers.sql")
    if not path.is_file():
        return False, "no top_customers.sql"
    db = sqlite3.connect(Path(d, "shop.db"))
    want = db.execute(EXPECTED).fetchall()
    try:
        got = db.execute(path.read_text().strip().rstrip(";")).fetchall()
    except sqlite3.Error as e:
        return False, f"the query fails: {e}"
    got = [(row[0], round(float(row[1]), 2)) for row in got if len(row) >= 2]
    return got == want, f"got {got}, expected {want}"
