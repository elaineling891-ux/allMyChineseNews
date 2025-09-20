import os
import re
from mysql.connector import pooling

# -------------------- 懒加载连接池 --------------------
_pool = None

def get_pool():
    """第一次调用时才真正建立连接池"""
    global _pool
    if _pool is None:
        DB_URL = os.getenv("DATABASE_URL")  # 格式: mysql://user:pass@host:port/db
        pattern = r'mysql://(.*?):(.*?)@(.*?):(\d+)/(.*)'
        m = re.match(pattern, DB_URL)
        if not m:
            raise ValueError("DATABASE_URL 格式错误")
        user, password, host, port, database = m.groups()

        # ⚠️ 免费 MySQL 通常 max_user_connections = 5
        _pool = pooling.MySQLConnectionPool(
            pool_name="mypool",
            pool_size=3,  # 留点余量，避免超过最大连接数
            user=user,
            password=password,
            host=host,
            port=int(port),
            database=database,
            charset="utf8mb4",
            auth_plugin="mysql_native_password"
        )
    return _pool


def get_conn():
    """从连接池获取连接"""
    return get_pool().get_connection()


# -------------------- 通用执行函数 --------------------
def execute(query, params=None, fetchone=False, fetchall=False, commit=False):
    conn, cur, result = None, None, None
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(query, params or ())
        if fetchone:
            result = cur.fetchone()
        elif fetchall:
            result = cur.fetchall()
        if commit:
            conn.commit()
        return result
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()  # 🔑 归还到连接池


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
    # 只在这里一次性设置时区和建表，避免重复开连接
    execute("SET time_zone = '+08:00';", commit=True)
    execute(query, commit=True)
    print("✅ 数据库初始化完成（created_at 默认 SGT）")


def insert_news(title, content, image_url=None, category='all'):
    if not title or not content:
        return
    query = """
        INSERT INTO news (title, content, image_url, category)
        VALUES (%s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE title=title
    """
    execute(query, (title, content, image_url, category), commit=True)


def update_news(news_id, title, content, image_url=None, category='all'):
    query = """
        UPDATE news
        SET title=%s, content=%s, image_url=%s, category=%s
        WHERE id=%s
    """
    execute(query, (title, content, image_url, category, news_id), commit=True)


def delete_news(news_id):
    query = "DELETE FROM news WHERE id=%s"
    execute(query, (news_id,), commit=True)


def get_all_news(skip=0, limit=20):
    query = """
        SELECT id, title, content, image_url, category, created_at
        FROM news
        ORDER BY created_at DESC
        LIMIT %s OFFSET %s
    """
    rows = execute(query, (limit, skip), fetchall=True)
    return [
        {
            "id": row[0],
            "title": row[1],
            "content": row[2],
            "image_url": row[3],
            "category": row[4],
            "created_at": row[5],
        }
        for row in rows
    ]


def get_news_by_id(news_id: int):
    query = """
        SELECT id, title, content, image_url, category, created_at
        FROM news
        WHERE id=%s
        LIMIT 1
    """
    row = execute(query, (news_id,), fetchone=True)
    if not row:
        return None
    return {
        "id": row[0],
        "title": row[1],
        "content": row[2],
        "image_url": row[3],
        "category": row[4],
        "created_at": row[5],
    }


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
    rows = execute(query, (category, limit, skip), fetchall=True)
    return [
        {
            "id": row[0],
            "title": row[1],
            "content": row[2],
            "image_url": row[3],
            "category": row[4],
            "created_at": row[5],
        }
        for row in rows
    ]


def get_all_db():
    cols = execute("DESCRIBE news", fetchall=True)
    columns = [col[0] for col in cols]
    rows = execute("SELECT * FROM news ORDER BY created_at DESC", fetchall=True)
    return columns, rows


def get_prev_news(news_id: int, category: str):
    query = """
        SELECT id, title 
        FROM news 
        WHERE id < %s AND category = %s
        ORDER BY id DESC 
        LIMIT 1
    """
    row = execute(query, (news_id, category), fetchone=True)
    return {"id": row[0], "title": row[1]} if row else None


def get_next_news(news_id: int, category: str):
    query = """
        SELECT id, title 
        FROM news 
        WHERE id > %s AND category = %s
        ORDER BY id ASC 
        LIMIT 1
    """
    row = execute(query, (news_id, category), fetchone=True)
    return {"id": row[0], "title": row[1]} if row else None
