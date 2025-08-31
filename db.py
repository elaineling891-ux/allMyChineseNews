import mysql.connector
import os
import re

DB_URL = os.getenv("DATABASE_URL")  # 格式: mysql://user:password@host:port/database

def get_conn():
    pattern = r'mysql://(.*?):(.*?)@(.*?):(\d+)/(.*)'
    m = re.match(pattern, DB_URL)
    if not m:
        raise ValueError("DATABASE_URL 格式错误")
    user, password, host, port, database = m.groups()
    conn = mysql.connector.connect(
        user=user,
        password=password,
        host=host,
        port=int(port),
        database=database,
        auth_plugin='mysql_native_password',
        charset='utf8mb4'
    )
    # 设置时区为新加坡
    cursor = conn.cursor()
    cursor.execute("SET time_zone = '+08:00';")
    cursor.close()
    return conn

def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS news (
        id INT AUTO_INCREMENT PRIMARY KEY,
        title TEXT,
        content TEXT,
        link VARCHAR(500),
        image_url TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE KEY unique_link (link(191)),
        UNIQUE KEY unique_title (title(191))
    ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
    """)
    conn.commit()
    cur.close()
    conn.close()
    print("✅ 数据库初始化完成（created_at 默认 SGT）")

def insert_news(title, content, link=None, image_url=None):
    if not title or not content:
        print("⚠️ 跳过插入：title 或 content 为空")
        return
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO news (title, content, link, image_url)
        VALUES (%s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE link=link
    """, (title, content, link, image_url))
    conn.commit()
    cur.close()
    conn.close()

def get_all_news(skip=0, limit=20):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, title, content, link, image_url, created_at
        FROM news
        ORDER BY created_at DESC
        LIMIT %s OFFSET %s
    """, (limit, skip))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    news = []
    for row in rows:
        news.append({
            "id": row[0],
            "title": row[1],
            "content": row[2],
            "link": row[3],
            "image_url": row[4],
            "created_at": row[5],  # 已是 SGT
        })
    return news

def get_news_by_id(news_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, title, content, link, image_url, created_at
        FROM news
        WHERE id=%s
        LIMIT 1
    """, (news_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        return None
    return {
        "id": row[0],
        "title": row[1],
        "content": row[2],
        "link": row[3],
        "image_url": row[4],
        "created_at": row[5],
    }

def news_exists(link: str) -> bool:
    if not link:
        return False
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM news WHERE link=%s LIMIT 1", (link,))
    exists = cur.fetchone() is not None
    cur.close()
    conn.close()
    return exists
    
def update_news(news_id, title, content, link=None, image_url=None):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        UPDATE news
        SET title=%s, content=%s, link=%s, image_url=%s
        WHERE id=%s
    """, (title, content, link, image_url, news_id))
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

def get_all_db():
    """返回所有字段名 + 所有行数据"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DESCRIBE news")
    columns = [col[0] for col in cur.fetchall()]
    cur.execute("SELECT * FROM news ORDER BY created_at DESC")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return columns, rows
