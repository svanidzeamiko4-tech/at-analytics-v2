import sqlite3

conn = sqlite3.connect("amiko_v3.db")
cur = conn.cursor()

print("=== შპს ორი ნაბიჯი (ქ.თბილისი,_ლილოს_დასახლება) — ინვოისები ===")
cur.execute(
    """
    SELECT i.id, i.invoice_number, i.source_file,
           i.total, COUNT(ii.id) as items
    FROM invoices i
    LEFT JOIN invoice_items ii ON ii.invoice_id = i.id
    JOIN stores s ON s.id = i.store_id
    WHERE s.address LIKE '%ლილოს_დასახლება%'
       OR s.address LIKE '%ლილოს დასახლება%'
    GROUP BY i.id
    ORDER BY i.total DESC
    LIMIT 10
"""
)
for r in cur.fetchall():
    print(f"id={r[0]} №{r[1]} file={r[2]} total={r[3]} items={r[4]}")

conn.close()
