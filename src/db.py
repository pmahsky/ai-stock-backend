import os
import sqlite3
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), "store.db")
print("📍 Using database:", os.path.abspath(DB_PATH))

STORE_DIRECTORY = [
    {
        "store_id": 101,
        "store_name": "Central Parent Store",
        "store_type": "PARENT",
        "parent_store_id": None,
    },
    {
        "store_id": 102,
        "store_name": "North Parent Store",
        "store_type": "PARENT",
        "parent_store_id": None,
    },
    {
        "store_id": 103,
        "store_name": "Campus Convenience Store",
        "store_type": "STORE",
        "parent_store_id": None,
    },
    {
        "store_id": 201,
        "store_name": "Central PFS",
        "store_type": "PFS",
        "parent_store_id": 101,
    },
    {
        "store_id": 204,
        "store_name": "North PFS",
        "store_type": "PFS",
        "parent_store_id": 101,
    },
    {
        "store_id": 301,
        "store_name": "Staff Canteen",
        "store_type": "CANTEEN",
        "parent_store_id": 101,
    },
]


def connect():
    return sqlite3.connect(DB_PATH)


def get_store_directory(query=None):
    if not query:
        return [dict(store) for store in STORE_DIRECTORY]

    needle = query.strip().lower()
    return [
        dict(store)
        for store in STORE_DIRECTORY
        if needle in str(store["store_id"])
        or needle in store["store_name"].lower()
        or needle in store["store_type"].lower()
    ]


def init_db():
    if os.path.exists(DB_PATH):
        print("🧹 Removing old database...")
        os.remove(DB_PATH)

    conn = connect()
    cur = conn.cursor()

    cur.execute(
        """
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
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS transfer_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_name TEXT NOT NULL,
            from_store INTEGER NOT NULL,
            to_store INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            transfer_type TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    stock_sample = [
        ("Milk 1L", 101, 90, "Dairy", "pack", 20, 35.0, "2026-11-20"),
        ("Bread", 101, 60, "Bakery", "pcs", 15, 25.0, "2026-09-09"),
        ("Chips", 101, 120, "Snacks", "pkt", 25, 20.0, "2027-03-01"),
        ("Coke 500ml", 101, 80, "Beverage", "bottle", 20, 45.0, "2026-12-31"),
        ("Cookies", 101, 48, "Snacks", "box", 12, 30.0, "2027-01-15"),
        ("Soap", 101, 30, "Toiletries", "pcs", 10, 60.0, "2027-06-01"),
        ("Milk 1L", 102, 18, "Dairy", "pack", 12, 35.0, "2026-11-20"),
        ("Bread", 102, 24, "Bakery", "pcs", 10, 25.0, "2026-09-09"),
        ("Chips", 102, 30, "Snacks", "pkt", 12, 20.0, "2027-03-01"),
        ("Milk 1L", 103, 8, "Dairy", "pack", 10, 35.0, "2026-11-20"),
        ("Bread", 103, 5, "Bakery", "pcs", 10, 25.0, "2026-09-09"),
        ("Soap", 103, 15, "Toiletries", "pcs", 10, 60.0, "2027-06-01"),
        ("Milk 1L", 201, 6, "Dairy", "pack", 10, 35.0, "2026-11-20"),
        ("Bread", 201, 4, "Bakery", "pcs", 8, 25.0, "2026-09-09"),
        ("Milk 1L", 204, 4, "Dairy", "pack", 10, 35.0, "2026-11-20"),
        ("Bread", 204, 3, "Bakery", "pcs", 8, 25.0, "2026-09-09"),
        ("Milk 1L", 301, 5, "Dairy", "pack", 10, 35.0, "2026-11-20"),
        ("Bread", 301, 3, "Bakery", "pcs", 8, 25.0, "2026-09-09"),
    ]

    cur.executemany(
        """
        INSERT INTO stock (product_name, store_id, quantity, category, uom, reorder_level, price, expiry_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        stock_sample,
    )

    now = datetime.utcnow()
    transfer_sample = []

    def add_transfer(product_name, from_store, to_store, quantity, transfer_type, days_ago):
        created_at = (now - timedelta(days=days_ago)).strftime("%Y-%m-%d %H:%M:%S")
        transfer_sample.append(
            (product_name, from_store, to_store, quantity, transfer_type, created_at)
        )

    # Parent -> PFS
    add_transfer("Milk 1L", 101, 201, 12, "PFS", 2)
    add_transfer("Milk 1L", 101, 201, 12, "PFS", 5)
    add_transfer("Milk 1L", 101, 201, 10, "PFS", 9)
    add_transfer("Milk 1L", 101, 201, 12, "PFS", 14)
    add_transfer("Bread", 101, 201, 8, "PFS", 3)
    add_transfer("Bread", 101, 201, 8, "PFS", 10)
    add_transfer("Bread", 101, 201, 6, "PFS", 17)
    add_transfer("Chips", 101, 201, 8, "PFS", 4)
    add_transfer("Chips", 101, 201, 6, "PFS", 11)
    add_transfer("Chips", 101, 201, 7, "PFS", 19)
    add_transfer("Coke 500ml", 101, 201, 5, "PFS", 35)  # ignored by cutoff
    add_transfer("Milk 1L", 101, 204, 10, "PFS", 3)
    add_transfer("Milk 1L", 101, 204, 12, "PFS", 8)
    add_transfer("Milk 1L", 101, 204, 10, "PFS", 15)
    add_transfer("Bread", 101, 204, 6, "PFS", 5)
    add_transfer("Bread", 101, 204, 6, "PFS", 12)
    add_transfer("Bread", 101, 204, 5, "PFS", 18)

    # Parent -> Staff canteen
    add_transfer("Milk 1L", 101, 301, 18, "CANTEEN", 1)
    add_transfer("Milk 1L", 101, 301, 18, "CANTEEN", 4)
    add_transfer("Milk 1L", 101, 301, 16, "CANTEEN", 8)
    add_transfer("Milk 1L", 101, 301, 18, "CANTEEN", 12)
    add_transfer("Milk 1L", 101, 301, 18, "CANTEEN", 18)
    add_transfer("Bread", 101, 301, 10, "CANTEEN", 2)
    add_transfer("Bread", 101, 301, 8, "CANTEEN", 6)
    add_transfer("Bread", 101, 301, 10, "CANTEEN", 13)
    add_transfer("Bread", 101, 301, 9, "CANTEEN", 20)
    add_transfer("Chips", 101, 301, 12, "CANTEEN", 7)
    add_transfer("Chips", 101, 301, 10, "CANTEEN", 15)
    add_transfer("Chips", 101, 301, 12, "CANTEEN", 21)
    add_transfer("Cookies", 101, 301, 6, "CANTEEN", 5)
    add_transfer("Cookies", 101, 301, 6, "CANTEEN", 9)
    add_transfer("Cookies", 101, 301, 5, "CANTEEN", 16)
    add_transfer("Soap", 101, 301, 2, "CANTEEN", 4)
    add_transfer("Soap", 101, 301, 12, "CANTEEN", 14)
    add_transfer("Soap", 101, 301, 1, "CANTEEN", 24)  # noisy, filtered

    cur.executemany(
        """
        INSERT INTO transfer_history (product_name, from_store, to_store, quantity, transfer_type, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        transfer_sample,
    )

    conn.commit()
    conn.close()
    print("✅ Fresh seed data inserted successfully (Stock + Transfers)")


def get_low_stock(store_id, threshold=10, product=None):
    conn = connect()
    cur = conn.cursor()

    if product:
        cur.execute(
            """
            SELECT product_name, quantity
            FROM stock
            WHERE store_id = ?
              AND lower(product_name) LIKE lower(?)
            ORDER BY product_name
            """,
            (store_id, f"%{product.strip()}%"),
        )
    else:
        cur.execute(
            """
            SELECT product_name, quantity
            FROM stock
            WHERE store_id = ?
              AND quantity < ?
            ORDER BY quantity ASC, product_name ASC
            """,
            (store_id, threshold),
        )

    rows = cur.fetchall()
    conn.close()

    results = []
    for product_name, quantity in rows:
        item = {"product": product_name, "qty": quantity}
        if product:
            item["is_low"] = quantity < threshold
        results.append(item)

    return results


def transfer_stock_record(product_name, from_store, to_store, quantity, transfer_type="MANUAL"):
    conn = connect()
    cur = conn.cursor()

    product_name = product_name.strip()
    transfer_type = transfer_type.strip().upper()

    cur.execute(
        """
        SELECT quantity
        FROM stock
        WHERE store_id = ?
          AND lower(trim(product_name)) = lower(?)
        """,
        (from_store, product_name),
    )
    row = cur.fetchone()

    if not row:
        conn.close()
        print(f"❌ Product '{product_name}' not found in store {from_store}")
        return f"product '{product_name}' not found in from_store"

    if row[0] < quantity:
        conn.close()
        print("❌ Insufficient quantity")
        return "insufficient quantity"

    cur.execute(
        """
        UPDATE stock
        SET quantity = quantity - ?,
            last_updated = CURRENT_TIMESTAMP
        WHERE store_id = ?
          AND lower(trim(product_name)) = lower(?)
        """,
        (quantity, from_store, product_name),
    )

    cur.execute(
        """
        SELECT quantity
        FROM stock
        WHERE store_id = ?
          AND lower(trim(product_name)) = lower(?)
        """,
        (to_store, product_name),
    )
    row2 = cur.fetchone()

    if row2:
        cur.execute(
            """
            UPDATE stock
            SET quantity = quantity + ?,
                last_updated = CURRENT_TIMESTAMP
            WHERE store_id = ?
              AND lower(trim(product_name)) = lower(?)
            """,
            (quantity, to_store, product_name),
        )
    else:
        cur.execute(
            """
            INSERT INTO stock (product_name, store_id, quantity)
            VALUES (?, ?, ?)
            """,
            (product_name, to_store, quantity),
        )

    cur.execute(
        """
        INSERT INTO transfer_history (product_name, from_store, to_store, quantity, transfer_type)
        VALUES (?, ?, ?, ?, ?)
        """,
        (product_name, from_store, to_store, quantity, transfer_type),
    )

    conn.commit()
    print(
        f"✅ Transfer committed (case-insensitive match): "
        f"{product_name} {quantity} {from_store}->{to_store} ({transfer_type})"
    )
    conn.close()
    return "transfer successful"


def get_stock_overview():
    conn = connect()
    cur = conn.cursor()
    total_items = cur.execute("SELECT COUNT(*) FROM stock").fetchone()[0]
    total_qty = cur.execute("SELECT SUM(quantity) FROM stock").fetchone()[0] or 0
    low_stock = cur.execute(
        "SELECT COUNT(*) FROM stock WHERE quantity < reorder_level"
    ).fetchone()[0]
    expiring = cur.execute(
        """
        SELECT COUNT(*) FROM stock
        WHERE expiry_date IS NOT NULL
          AND DATE(expiry_date) <= DATE('now', '+7 day')
        """
    ).fetchone()[0]
    conn.close()
    return {
        "total_items": total_items,
        "total_quantity": total_qty,
        "low_stock": low_stock,
        "expiring": expiring,
    }


def update_stock(product_name, store_id, delta_qty):
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE stock
        SET quantity = quantity + ?,
            last_updated = CURRENT_TIMESTAMP
        WHERE product_name = ?
          AND store_id = ?
        """,
        (delta_qty, product_name, store_id),
    )
    conn.commit()
    conn.close()


def get_unique_product_names():
    conn = connect()
    cur = conn.cursor()
    rows = cur.execute("SELECT DISTINCT product_name FROM stock ORDER BY product_name").fetchall()
    conn.close()
    return [row[0] for row in rows]


def get_product_details(product_name, store_id=None):
    conn = connect()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    product_name = product_name.strip()

    if store_id:
        cur.execute(
            """
            SELECT product_name, store_id, quantity, price, uom, category
            FROM stock
            WHERE lower(trim(product_name)) = lower(?)
              AND store_id = ?
            """,
            (product_name, store_id),
        )
    else:
        cur.execute(
            """
            SELECT product_name, store_id, quantity, price, uom, category
            FROM stock
            WHERE lower(trim(product_name)) = lower(?)
            ORDER BY store_id
            """,
            (product_name,),
        )

    rows = cur.fetchall()
    conn.close()

    return [
        {
            "product": row["product_name"],
            "store_id": row["store_id"],
            "qty": row["quantity"],
            "price": row["price"],
            "uom": row["uom"],
            "category": row["category"],
        }
        for row in rows
    ]


def _build_transfer_reason(frequency, days_since_last, quantity_spread_ratio):
    frequent = frequency >= 4
    recent = days_since_last <= 7
    consistent = quantity_spread_ratio <= 0.3

    if frequent and recent and consistent:
        return "frequently transferred recently"
    if frequent and recent:
        return "frequently transferred in the last 2 weeks"
    if frequent:
        return "repeated transfer pattern in the last month"
    if recent:
        return "recent repeat transfer pattern"
    return "historical transfer pattern"


def get_transfer_recommendations(from_store, to_store, transfer_type, days=30):
    conn = connect()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    transfer_type = transfer_type.strip().upper()
    cutoff_date = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")

    print(
        f"🔍 Analyzing transfers since {cutoff_date} for "
        f"{from_store}->{to_store} [{transfer_type}]"
    )

    query = """
        SELECT
            th.product_name,
            COUNT(*) AS frequency,
            AVG(th.quantity) AS avg_qty,
            MIN(th.quantity) AS min_qty,
            MAX(th.quantity) AS max_qty,
            MAX(th.created_at) AS last_transferred_at,
            CAST(julianday('now') - julianday(MAX(th.created_at)) AS REAL) AS days_since_last,
            s.quantity AS source_stock,
            s.reorder_level AS reorder_level
        FROM transfer_history th
        JOIN stock s
          ON s.store_id = th.from_store
         AND lower(trim(s.product_name)) = lower(trim(th.product_name))
        WHERE th.from_store = ?
          AND th.to_store = ?
          AND upper(th.transfer_type) = ?
          AND th.created_at >= ?
        GROUP BY th.product_name, s.quantity, s.reorder_level
        HAVING COUNT(*) >= 3
        ORDER BY MAX(th.created_at) DESC, COUNT(*) DESC
    """

    cur.execute(query, (from_store, to_store, transfer_type, cutoff_date))
    rows = cur.fetchall()
    conn.close()

    suggestions = []
    for row in rows:
        avg_qty = float(row["avg_qty"] or 0)
        if avg_qty <= 0:
            continue

        quantity_spread_ratio = (row["max_qty"] - row["min_qty"]) / avg_qty
        if quantity_spread_ratio > 0.75:
            continue

        source_stock = int(row["source_stock"] or 0)
        reorder_level = int(row["reorder_level"] or 0)
        available_to_transfer = max(source_stock - reorder_level, 0)
        if available_to_transfer <= 0:
            continue

        suggested_qty = min(max(int(round(avg_qty)), 1), available_to_transfer)
        if suggested_qty <= 0:
            continue

        frequency = int(row["frequency"])
        days_since_last = max(float(row["days_since_last"] or days), 0.0)
        frequency_score = min(frequency / 6.0, 1.0)
        recency_score = max(0.0, 1.0 - (days_since_last / days))

        if quantity_spread_ratio <= 0.25:
            consistency_multiplier = 1.0
        elif quantity_spread_ratio <= 0.5:
            consistency_multiplier = 0.9
        else:
            consistency_multiplier = 0.75

        score = round(
            min(
                max((frequency_score * 0.7 + recency_score * 0.3) * consistency_multiplier, 0.0),
                1.0,
            ),
            2,
        )

        if score >= 0.8 and frequency >= 4:
            confidence = "high"
        elif score >= 0.55:
            confidence = "medium"
        else:
            confidence = "low"

        suggestions.append(
            {
                "product": row["product_name"],
                "suggested_qty": suggested_qty,
                "frequency": frequency,
                "score": score,
                "confidence": confidence,
                "reason": _build_transfer_reason(
                    frequency,
                    days_since_last,
                    quantity_spread_ratio,
                ),
            }
        )

    return suggestions


if __name__ == "__main__":
    init_db()
