import os, sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), "store.db")
print("📍 Using database:", os.path.abspath(DB_PATH))


def connect():
    return sqlite3.connect(DB_PATH)

def init_db():
    if os.path.exists(DB_PATH):
        print("🧹 Removing old database...")
        os.remove(DB_PATH)

    conn = connect()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS stock (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_name TEXT NOT NULL,
        store_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL,
        category TEXT,
        uom TEXT DEFAULT 'pcs',
        reorder_level INTEGER DEFAULT 10,
        price REAL DEFAULT 0.0,
        expiry_date TEXT,
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    sample = [
        ('Coke 500ml', 101, 5, 'Beverage', 'bottle', 10, 45.0, '2025-12-31'),
        ('Chips', 101, 50, 'Snacks', 'pkt', 15, 20.0, '2026-03-01'),
        ('Milk 1L', 102, 8, 'Dairy', 'pack', 12, 35.0, '2025-11-20'),
        ('Bread', 103, 2, 'Bakery', 'pcs', 10, 25.0, '2025-11-09'),
        ('Soap', 103, 15, 'Toiletries', 'pcs', 10, 60.0, '2027-01-01')
    ]

    cur.executemany("""
        INSERT INTO stock (product_name, store_id, quantity, category, uom, reorder_level, price, expiry_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, sample)

    conn.commit()
    conn.close()
    print("✅ Fresh seed data inserted successfully")




def get_low_stock(store_id, threshold=10):
    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT product_name, quantity FROM stock WHERE store_id=? AND quantity<?", (store_id, threshold))
    rows = cur.fetchall()
    conn.close()
    return [{"product": r[0], "qty": r[1]} for r in rows]

def transfer_stock_record(product_name, from_store, to_store, quantity):
    conn = connect()
    cur = conn.cursor()

    # Clean up the product name to avoid space/case mismatches
    product_name = product_name.strip()

    # ↓ Case-insensitive SELECT for from_store
    cur.execute("""
        SELECT quantity
        FROM stock
        WHERE store_id = ?
          AND lower(trim(product_name)) = lower(?)
    """, (from_store, product_name))
    row = cur.fetchone()

    if not row:
        conn.close()
        print(f"❌ Product '{product_name}' not found in store {from_store}")
        return f"product '{product_name}' not found in from_store"

    if row[0] < quantity:
        conn.close()
        print("❌ Insufficient quantity")
        return "insufficient quantity"

    # ↓ Case-insensitive UPDATE for from_store
    cur.execute("""
        UPDATE stock
        SET quantity = quantity - ?
        WHERE store_id = ?
          AND lower(trim(product_name)) = lower(?)
    """, (quantity, from_store, product_name))

    # ↓ Case-insensitive SELECT for to_store
    cur.execute("""
        SELECT quantity
        FROM stock
        WHERE store_id = ?
          AND lower(trim(product_name)) = lower(?)
    """, (to_store, product_name))
    row2 = cur.fetchone()

    if row2:
        cur.execute("""
            UPDATE stock
            SET quantity = quantity + ?
            WHERE store_id = ?
              AND lower(trim(product_name)) = lower(?)
        """, (quantity, to_store, product_name))
    else:
        cur.execute("""
            INSERT INTO stock (product_name, store_id, quantity)
            VALUES (?, ?, ?)
        """, (product_name, to_store, quantity))

    conn.commit()
    print(f"✅ Transfer committed (case-insensitive match): {product_name} {quantity} {from_store}->{to_store}")
    conn.close()
    return "transfer successful"


def get_stock_overview():
    conn = connect()
    cur = conn.cursor()
    total_items = cur.execute("SELECT COUNT(*) FROM stock").fetchone()[0]
    total_qty = cur.execute("SELECT SUM(quantity) FROM stock").fetchone()[0] or 0
    low_stock = cur.execute("SELECT COUNT(*) FROM stock WHERE quantity < reorder_level").fetchone()[0]
    expiring = cur.execute("""
        SELECT COUNT(*) FROM stock
        WHERE expiry_date IS NOT NULL
          AND DATE(expiry_date) <= DATE('now', '+7 day')
    """).fetchone()[0]
    conn.close()
    return {
        "total_items": total_items,
        "total_quantity": total_qty,
        "low_stock": low_stock,
        "expiring": expiring
    }

def update_stock(product_name, store_id, delta_qty):
    conn = connect()
    cur = conn.cursor()
    cur.execute("""
        UPDATE stock SET quantity = quantity + ?, last_updated=CURRENT_TIMESTAMP
        WHERE product_name=? AND store_id=?
    """, (delta_qty, product_name, store_id))
    conn.commit()
    conn.close()
    # notify_clients({"product": product_name, "store": store_id})

    if __name__ == "__main__":
        init_db()





