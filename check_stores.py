import sqlite3
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

conn = sqlite3.connect("amiko_v3.db")
cur = conn.execute("PRAGMA table_info(stores)")
for row in cur:
    print(row)
print("---")
cur2 = conn.execute("SELECT * FROM stores LIMIT 3")
for row in cur2:
    print(row)
conn.close()
