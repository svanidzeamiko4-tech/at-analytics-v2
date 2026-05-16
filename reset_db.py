import sqlite3

conn = sqlite3.connect("amiko_v3.db")
conn.execute("PRAGMA foreign_keys = ON")
conn.execute("DELETE FROM invoice_items")
conn.execute("DELETE FROM invoices")
conn.execute("DELETE FROM stores")
conn.commit()
print("Database cleared")
conn.close()
