import os
import psycopg2

DATABASE_URL = os.getenv("DATABASE_URL")

def init_db():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS news (
            id SERIAL PRIMARY KEY,
            title TEXT,
            link TEXT
        );
    """)
    conn.commit()
    cur.close()
    conn.close()

def insert_news(item):
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute("INSERT INTO news (title, link) VALUES (%s, %s)", (item['title'], item['link']))
    conn.commit()
    cur.close()
    conn.close()

def get_db():
    return psycopg2.connect(DATABASE_URL)
