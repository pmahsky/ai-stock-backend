import sqlite3
from tabulate import tabulate

DB_PATH = "store.db"

def connect():
    return sqlite3.connect(DB_PATH)

def show_all_stores():
    conn = connect()
    cur = conn.cursor()

    # Get all distinct store IDs
    stores = cur.execute("SELECT DISTINCT store_id FROM stock ORDER BY store_id").fetchall()
    print("\n📦 Current Store Summary\n========================")
    for (sid,) in stores:
        print(f"\n🏬 Store {sid}:")
        rows = cur.execute("""
            SELECT product_name, quantity, category, uom, price, expiry_date
            FROM stock WHERE store_id=? ORDER BY product_name
        """, (sid,)).fetchall()
        print(tabulate(rows, headers=["Product", "Qty", "Category", "UoM", "Price", "Expiry"]))
    conn.close()

def show_summary():
    conn = connect()
    cur = conn.cursor()
    stats = cur.execute("""
        SELECT COUNT(*), SUM(quantity),
               SUM(CASE WHEN quantity < reorder_level THEN 1 ELSE 0 END)
        FROM stock
    """).fetchone()
    print("\n📊 Summary\n==========")
    print(f"Total items: {stats[0]}")
    print(f"Total quantity: {stats[1]}")
    print(f"Low stock count: {stats[2]}")
    conn.close()

if __name__ == "__main__":
    print(f"Inspecting {DB_PATH}")
    show_summary()
    show_all_stores()
