import os
import re
import mysql.connector

# -------------------- 获取连接 --------------------
def get_conn():
    """每次都新建连接，用完即关（适合 Render 免费 MySQL）"""
    DB_URL = os.getenv("DATABASE_URL")  # 格式: mysql://user:pass@host:port/db
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
        charset="utf8mb4",
        auth_plugin="mysql_native_password"
    )
    return conn


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
            conn.close()  # 🔑 确保释放


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
    execute("SET time_zone = '+08:00';")
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
