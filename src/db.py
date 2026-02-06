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

    cur.execute("""
    CREATE TABLE IF NOT EXISTS transfer_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_name TEXT NOT NULL,
        from_store INTEGER NOT NULL,
        to_store INTEGER NOT NULL,
        quantity INTEGER NOT NULL,
        transfer_type TEXT NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
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

    # Seed Transfer History for Recommendations
    transfer_sample = [
        ('Milk 1L', 102, 201, 10, 'CANTEEN'),
        ('Milk 1L', 102, 201, 10, 'CANTEEN'),
        ('Milk 1L', 102, 201, 10, 'CANTEEN'),
        ('Milk 1L', 102, 201, 10, 'CANTEEN'),
        ('Bread', 103, 201, 2, 'CANTEEN'),
        ('Cookies', 101, 201, 5, 'CANTEEN')
    ]
    
    cur.executemany("""
        INSERT INTO transfer_history (product_name, from_store, to_store, quantity, transfer_type)
        VALUES (?, ?, ?, ?, ?)
    """, transfer_sample)

    conn.commit()
    conn.close()
    print("✅ Fresh seed data inserted successfully (Stock + Transfers)")




def get_low_stock(store_id, threshold=10, product=None):
    conn = connect()
    cur = conn.cursor()
    if product:
        cur.execute("SELECT product_name, quantity FROM stock WHERE store_id=? AND product_name LIKE ?", (store_id, f"%{product}%"))
    else:
        cur.execute("SELECT product_name, quantity FROM stock WHERE store_id=? AND quantity<?", (store_id, threshold))
    
    rows = cur.fetchall()
    conn.close()
    
    # If checking a specific product, we return it regardless of quantity so the caller can decide if it's "low" or not
    # based on the threshold. Or we can filter here. 
    # The requirement is: "even if its not low in stock". So we should return it.
    
    results = []
    for r in rows:
        qty = r[1]
        is_low = qty < threshold
        if product:
             # If specific product asked, return it even if not low, but mark status
             results.append({"product": r[0], "qty": qty, "is_low": is_low})
        else:
            # If general check, only return actual low items
             results.append({"product": r[0], "qty": qty})
             
    return results

def transfer_stock_record(product_name, from_store, to_store, quantity, transfer_type="MANUAL"):
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

    cur.execute("""
        INSERT INTO transfer_history (product_name, from_store, to_store, quantity, transfer_type)
        VALUES (?, ?, ?, ?, ?)
    """, (product_name, from_store, to_store, quantity, transfer_type))

    conn.commit()
    print(f"✅ Transfer committed (case-insensitive match): {product_name} {quantity} {from_store}->{to_store} ({transfer_type})")
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

def get_unique_product_names():
    """Return a list of distinct product names from the database."""
    conn = connect()
    cur = conn.cursor()
    rows = cur.execute("SELECT DISTINCT product_name FROM stock").fetchall()
    conn.close()
    return [r[0] for r in rows]

def get_product_details(product_name, store_id=None):
    """
    Get details for a product.
    If store_id is provided, returns list containing that specific store's entry (if found).
    If store_id is None, returns list of all stores containing the product.
    """
    conn = connect()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    product_name = product_name.strip()

    if store_id:
        cur.execute("""
            SELECT product_name, store_id, quantity, price, uom, category 
            FROM stock 
            WHERE lower(trim(product_name)) = lower(?) AND store_id = ?
        """, (product_name, store_id))
    else:
        cur.execute("""
            SELECT product_name, store_id, quantity, price, uom, category 
            FROM stock 
            WHERE lower(trim(product_name)) = lower(?)
            ORDER BY store_id
        """, (product_name,))

    rows = cur.fetchall()
    conn.close()
    
    results = []
    for r in rows:
        results.append({
            "product": r["product_name"],
            "store_id": r["store_id"],
            "qty": r["quantity"],
            "price": r["price"],
            "uom": r["uom"],
            "category": r["category"]
        })
    return results

def get_transfer_recommendations(from_store, to_store, transfer_type, days=30):
    conn = connect()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    # Calculate cutoff date
    cur.execute("SELECT date('now', ? || ' days')", (f'-{days}',))
    cutoff_date = cur.fetchone()[0]

    print(f"🔍 Analyzing transfers since {cutoff_date} for {from_store}->{to_store} [{transfer_type}]")

    query = """
        SELECT 
            product_name,
            COUNT(*) as frequency,
            AVG(quantity) as avg_qty
        FROM transfer_history
        WHERE from_store = ? 
          AND to_store = ? 
          AND transfer_type = ?
          AND created_at >= ?
        GROUP BY product_name
        HAVING frequency >= 3
        ORDER BY frequency DESC
    """
    
    cur.execute(query, (from_store, to_store, transfer_type, cutoff_date))
    rows = cur.fetchall()
    conn.close()
    
    suggestions = []
    for row in rows:
        suggestions.append({
            "product": row["product_name"],
            "suggested_qty": int(row["avg_qty"]),
            "frequency": row["frequency"],
            "reason": f"Transferred {row['frequency']} times in last {days} days"
        })
        
    return suggestions

    if __name__ == "__main__":
        init_db()





