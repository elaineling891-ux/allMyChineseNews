import os
import re
from mysql.connector import pooling
from contextlib import contextmanager

# -------------------- 懒加载连接池 --------------------
_pool = None

def get_pool():
    """第一次调用时才真正建立连接池"""
    global _pool
    if _pool is None:
        DB_URL = os.getenv("DATABASE_URL")  # 格式: mysql://user:password@host:port/database
        pattern = r"mysql://(.*?):(.*?)@(.*?):(\d+)/(.*)"
        m = re.match(pattern, DB_URL)
        if not m:
            raise ValueError("DATABASE_URL 格式错误")
        user, password, host, port, database = m.groups()

        max_conn = int(os.getenv("MAX_CONNECTIONS", "5"))  # Render 免费 MySQL 一般是 5
        safe_pool_size = max(1, max_conn // 2)

        _pool = pooling.MySQLConnectionPool(
            pool_name="mypool",
            pool_size=safe_pool_size,
            pool_reset_session=True,
            user=user,
            password=password,
            host=host,
            port=int(port),
            database=database,
            charset="utf8mb4",
            auth_plugin="mysql_native_password",
        )
        print(f"✅ MySQL 连接池初始化完成，pool_size={safe_pool_size}")
    return _pool


@contextmanager
def get_conn():
    """获取一个连接（自动 close）"""
    conn = None
    try:
        conn = get_pool().get_connection()
        yield conn
    finally:
        if conn:
            conn.close()


# -------------------- 数据库操作 --------------------

def init_db():
    query = """
    CREATE TABLE IF NOT EXISTS news (
        id INT AUTO_INCREMENT PRIMARY KEY,
        title TEXT,
        content TEXT,
        image_url TEXT,
        category VARCHAR(100) DEFAULT 'all',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE KEY unique_title (title(191))
    ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
    """
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SET time_zone = '+08:00';")
        cur.execute(query)
        conn.commit()
        cur.close()
    print("✅ 数据库初始化完成（created_at 默认 SGT）")


def insert_news(title, content, image_url=None, category="all"):
    if not title or not content:
        return
    query = """
        INSERT INTO news (title, content, image_url, category)
        VALUES (%s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE title=title
    """
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(query, (title, content, image_url, category))
        conn.commit()
        cur.close()


def update_news(news_id, title, content, image_url=None, category="all"):
    query = """
        UPDATE news
        SET title=%s, content=%s, image_url=%s, category=%s
        WHERE id=%s
    """
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(query, (title, content, image_url, category, news_id))
        conn.commit()
        cur.close()


def delete_news(news_id):
    query = "DELETE FROM news WHERE id=%s"
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(query, (news_id,))
        conn.commit()
        cur.close()


def get_all_news(skip=0, limit=20):
    query = """
        SELECT id, title, content, image_url, category, created_at
        FROM news
        ORDER BY created_at DESC
        LIMIT %s OFFSET %s
    """
    with get_conn() as conn:
        cur = conn.cursor(dictionary=True)
        cur.execute(query, (limit, skip))
        rows = cur.fetchall()
        cur.close()
        return rows


def get_news_by_id(news_id: int):
    query = """
        SELECT id, title, content, image_url, category, created_at
        FROM news
        WHERE id=%s
        LIMIT 1
    """
    with get_conn() as conn:
        cur = conn.cursor(dictionary=True)
        cur.execute(query, (news_id,))
        row = cur.fetchone()
        cur.close()
        return row


def get_all_news_by_category(category: str, skip=0, limit=20):
    if category.lower() == "all":
        return get_all_news(skip, limit)
    query = """
        SELECT id, title, content, image_url, category, created_at
        FROM news
        WHERE category=%s
        ORDER BY created_at DESC
        LIMIT %s OFFSET %s
    """
    with get_conn() as conn:
        cur = conn.cursor(dictionary=True)
        cur.execute(query, (category, limit, skip))
        rows = cur.fetchall()
        cur.close()
        return rows


def get_all_db():
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("DESCRIBE news")
        columns = [col[0] for col in cur.fetchall()]
        cur.execute("SELECT * FROM news ORDER BY created_at DESC")
        rows = cur.fetchall()
        cur.close()
    return columns, rows


def get_prev_news(news_id: int, category: str):
    query = """
        SELECT id, title 
        FROM news 
        WHERE id < %s AND category = %s
        ORDER BY id DESC 
        LIMIT 1
    """
    with get_conn() as conn:
        cur = conn.cursor(dictionary=True)
        cur.execute(query, (news_id, category))
        row = cur.fetchone()
        cur.close()
        return row


def get_next_news(news_id: int, category: str):
    query = """
        SELECT id, title 
        FROM news 
        WHERE id > %s AND category = %s
        ORDER BY id ASC 
        LIMIT 1
    """
    with get_conn() as conn:
        cur = conn.cursor(dictionary=True)
        cur.execute(query, (news_id, category))
        row = cur.fetchone()
        cur.close()
        return row
