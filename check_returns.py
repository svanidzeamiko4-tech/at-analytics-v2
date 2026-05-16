import sqlite3

conn = sqlite3.connect("amiko_v3.db")
cur = conn.cursor()

print("=== დაბრუნების ინვოისები ===")
cur.execute(
    """
    SELECT i.id, i.invoice_number, i.notes, i.total,
           s.name, COUNT(ii.id) as items
    FROM invoices i
    JOIN stores s ON s.id = i.store_id
    LEFT JOIN invoice_items ii ON ii.invoice_id = i.id
    WHERE i.notes LIKE '%უკან დაბრუნება%'
       OR i.invoice_number LIKE '%CR%'
       OR i.notes LIKE '%return%'
    GROUP BY i.id
    ORDER BY i.total DESC
    LIMIT 20
"""
)
for r in cur.fetchall():
    print(f"id={r[0]} №{r[1]} total={r[3]} store={r[4]} items={r[5]}")
    print(f"  notes: {str(r[2])[:100]}")

print()
print("=== invoice_items line_total უარყოფითი ===")
cur.execute(
    """
    SELECT COUNT(*), SUM(line_total)
    FROM invoice_items
    WHERE line_total < 0
"""
)
r = cur.fetchone()
print(f"უარყოფითი ხაზები: {r[0]}, სულ: {r[1]}")

print()
print("=== notes-ში 'უკან' შემცველი ინვოისები ===")
cur.execute(
    """
    SELECT COUNT(*) FROM invoices
    WHERE notes LIKE '%უკან%'
"""
)
print(f"ინვოისები: {cur.fetchone()[0]}")

conn.close()
