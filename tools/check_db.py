import sqlite3
import os
import glob

dbs = glob.glob('data/*.db') + glob.glob('storage/*.db')
print('Found DBs:', dbs)
for db in dbs:
    conn = sqlite3.connect(db)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cur.fetchall()
    print(f'DB {db}: tables = {tables}')
    for t in tables:
        tname = t[0]
        cur.execute(f"SELECT COUNT(*) FROM {tname};")
        cnt = cur.fetchone()[0]
        print(f'  Table {tname}: count = {cnt}')
