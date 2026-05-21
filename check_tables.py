import sqlite3

conn = sqlite3.connect("amiko_v3.db")
tables = [
    r[0]
    for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
]
print(tables)
conn.close()
