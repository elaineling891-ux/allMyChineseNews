import os
import re
from mysql.connector import pooling

# -------------------- 懒加载连接池 --------------------
_pool = None

def get_pool():
    """第一次调用时才真正建立连接池"""
    global _pool
    if _pool is None:
        DB_URL = os.getenv("DATABASE_URL")  # 格式: mysql://user:password@host:port/database
        pattern = r'mysql://(.*?):(.*?)@(.*?):(\d+)/(.*)'
        m = re.match(pattern, DB_URL)
        if not m:
            raise ValueError("DATABASE_URL 格式错误")
        user, password, host, port, database = m.groups()

        # Render 免费 MySQL 建议 pool_size = 1
        safe_pool_size = 1

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
            auth_plugin="mysql_native_password"
        )
        print(f"✅ MySQL 连接池初始化完成，pool_size={safe_pool_size}")
    return _pool

def get_conn():
    """获取一个连接（用完要记得 close()）"""
    return get_pool().get_connection()

# -------------------- 通用执行函数 --------------------

def execute(query, params=None, fetchone=False, fetchall=False, commit=False):
    conn = None
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(query, params or ())
        result = None
        if fetchone:
            result = cur.fetchone()
        elif fetchall:
            result = cur.fetchall()
        if commit:
            conn.commit()
        cur.close()
        return result
    finally:
        if conn:
            conn.close()  # 🔑 关键：确保释放回连接池

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
    execute("SET time_zone = '+08:00';", commit=True)
    execute(query, commit=True)
    print("✅ 数据库初始化完成（created_at 默认 SGT）")

def insert_news(title, content, image_url=None, category='all'):
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
    execute("DELETE FROM news WHERE id=%s", (news_id,), commit=True)

def get_all_news(skip=0, limit=20):
    query = """
        SELECT id, title, content, image_url, category, created_at
        FROM news
        ORDER BY created_at DESC
        LIMIT %s OFFSET %s
    """
    rows = execute(query, (limit, skip), fetchall=True)
    return [
        {"id": r[0], "title": r[1], "content": r[2], "image_url": r[3], "category": r[4], "created_at": r[5]}
        for r in rows
    ]

def get_news_by_id(news_id: int):
    query = """
        SELECT id, title, content, image_url, category, created_at
        FROM news
        WHERE id=%s LIMIT 1
    """
    row = execute(query, (news_id,), fetchone=True)
    return {"id": row[0], "title": row[1], "content": row[2], "image_url": row[3], "category": row[4], "created_at": row[5]} if row else None

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
        {"id": r[0], "title": r[1], "content": r[2], "image_url": r[3], "category": r[4], "created_at": r[5]}
        for r in rows
    ]

def get_all_db():
    columns = [c[0] for c in execute("DESCRIBE news", fetchall=True)]
    rows = execute("SELECT * FROM news ORDER BY created_at DESC", fetchall=True)
    return columns, rows

def get_prev_news(news_id: int, category: str):
    query = """
        SELECT id, title FROM news 
        WHERE id < %s AND category = %s
        ORDER BY id DESC LIMIT 1
    """
    row = execute(query, (news_id, category), fetchone=True)
    return {"id": row[0], "title": row[1]} if row else None

def get_next_news(news_id: int, category: str):
    query = """
        SELECT id, title FROM news 
        WHERE id > %s AND category = %s
        ORDER BY id ASC LIMIT 1
    """
    row = execute(query, (news_id, category), fetchone=True)
    return {"id": row[0], "title": row[1]} if row else None
