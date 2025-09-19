import mysql.connector
from mysql.connector import pooling
import os
import re

DB_URL = os.getenv("DATABASE_URL")  # 格式: mysql://user:password@host:port/database

# ---------------- 解析数据库 URL ----------------
pattern = r'mysql://(.*?):(.*?)@(.*?):(\d+)/(.*)'
m = re.match(pattern, DB_URL)
if not m:
    raise ValueError("DATABASE_URL 格式错误")
user, password, host, port, database = m.groups()

# ---------------- 初始化连接池 ----------------
pool = pooling.MySQLConnectionPool(
    pool_name="mypool",
    pool_size=10,  # 可根据服务器能力调整
    user=user,
    password=password,
    host=host,
    port=int(port),
    database=database,
    charset='utf8mb4',
    auth_plugin='mysql_native_password'
)

# ---------------- 获取连接 ----------------
def get_conn():
    conn = pool.get_connection()
    cursor = conn.cursor()
    cursor.execute("SET time_zone = '+08:00';")
    cursor.close()
    return conn

# ---------------- CRUD 函数 ----------------
def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS news (
        id INT AUTO_INCREMENT PRIMARY KEY,
        title TEXT,
        content TEXT,
        image_url TEXT,
        category VARCHAR(100) DEFAULT 'all',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE KEY unique_title (title(191))
    ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
    """)
    conn.commit()
    cur.close()
    conn.close()
    print("✅ 数据库初始化完成（created_at 默认 SGT）")

def insert_news(title, content, image_url=None, category='all'):
    if not title or not content:
        return
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO news (title, content, image_url, category)
        VALUES (%s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE title=title
    """, (title, content, image_url, category))
    conn.commit()
    cur.close()
    conn.close()

def update_news(news_id, title, content, image_url=None, category='all'):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        UPDATE news
        SET title=%s, content=%s, image_url=%s, category=%s
        WHERE id=%s
    """, (title, content, image_url, category, news_id))
    conn.commit()
    cur.close()
    conn.close()

def delete_news(news_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM news WHERE id=%s", (news_id,))
    conn.commit()
    cur.close()
    conn.close()

def get_all_news(skip=0, limit=20):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, title, content, image_url, category, created_at
        FROM news
        ORDER BY created_at DESC
        LIMIT %s OFFSET %s
    """, (limit, skip))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [
        {"id": r[0], "title": r[1], "content": r[2],
         "image_url": r[3], "category": r[4], "created_at": r[5]}
        for r in rows
    ]

def get_news_by_id(news_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, title, content, image_url, category, created_at
        FROM news
        WHERE id=%s
        LIMIT 1
    """, (news_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        return None
    return {"id": row[0], "title": row[1], "content": row[2],
            "image_url": row[3], "category": row[4], "created_at": row[5]}

def get_all_news_by_category(category: str, skip=0, limit=20):
    conn = get_conn()
    cur = conn.cursor()
    if category.lower() == "all":
        cur.execute("""
            SELECT id, title, content, image_url, category, created_at
            FROM news
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
        """, (limit, skip))
    else:
        cur.execute("""
            SELECT id, title, content, image_url, category, created_at
            FROM news
            WHERE category=%s
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
        """, (category, limit, skip))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [
        {"id": r[0], "title": r[1], "content": r[2],
         "image_url": r[3], "category": r[4], "created_at": r[5]}
        for r in rows
    ]

def get_prev_news(news_id: int, category: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, title 
        FROM news 
        WHERE id < %s AND category = %s
        ORDER BY id DESC 
        LIMIT 1
    """, (news_id, category))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return {"id": row[0], "title": row[1]} if row else None

def get_next_news(news_id: int, category: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, title 
        FROM news 
        WHERE id > %s AND category = %s
        ORDER BY id ASC 
        LIMIT 1
    """, (news_id, category))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return {"id": row[0], "title": row[1]} if row else None
