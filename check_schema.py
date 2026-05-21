import sqlite3
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

conn = sqlite3.connect("amiko_v3.db")
print("=== stores ===")
for row in conn.execute("PRAGMA table_info(stores)"):
    print(row)
print("=== stores data ===")
for row in conn.execute("SELECT * FROM stores LIMIT 3"):
    print(row)
print("=== users/distributors ===")
tables = [
    r[0]
    for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
]
for t in tables:
    if "user" in t.lower() or "dist" in t.lower() or "auth" in t.lower():
        print("TABLE:", t)
        for row in conn.execute(f"PRAGMA table_info({t})"):
            print(row)
conn.close()
