import asyncio
import os
from fastapi import FastAPI, Request, Form, Path
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse, FileResponse
from fastapi.templating import Jinja2Templates
from db import get_all_news, init_db, get_news_by_id, insert_news, update_news, delete_news, get_all_db, get_all_news_by_category, get_news_by_id, get_prev_news, get_next_news
from harvest import fetch_news
from datetime import datetime
import requests

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# -------------------------- 启动事件 --------------------------
@app.on_event("startup")
async def startup_event():
    init_db()
    init_sitemap()
    asyncio.create_task(periodic_keep_alive(300))

import os

SITEMAP_PATH = "sitemap.xml"

def init_sitemap():
    if os.path.exists(SITEMAP_PATH):
        return

    columns, rows = get_all_db()  # rows 是原始数据
    # 找出列对应的索引
    idx_id = columns.index("id")
    idx_created = columns.index("created_at")

    sitemap_items = ""
    for row in rows:
        news_id = row[idx_id]
        created_at = row[idx_created]
        # 如果是 datetime 对象
        if hasattr(created_at, "strftime"):
            lastmod = created_at.strftime("%Y-%m-%dT%H:%M:%S+08:00")
        else:
            lastmod = str(created_at)
        url = f"https://www.mychinesenews.my/news/{news_id}"
        sitemap_items += f"""
  <url>
    <loc>{url}</loc>
    <lastmod>{lastmod}</lastmod>
    <changefreq>daily</changefreq>
    <priority>0.8</priority>
  </url>"""

    sitemap_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{sitemap_items}
</urlset>"""

    with open(SITEMAP_PATH, "w", encoding="utf-8") as f:
        f.write(sitemap_content)

@app.get("/sitemap.xml", response_class=FileResponse)
async def sitemap_xml():
    return FileResponse(SITEMAP_PATH, media_type="application/xml")

async def periodic_fetch_news(interval=43200):
    while True:
        try:
            print(f"⏳ [{datetime.now()}] 开始抓新闻...")
            await asyncio.get_event_loop().run_in_executor(None, fetch_news)
            print(f"✅ [{datetime.now()}] 抓新闻完成")
        except Exception as e:
            print("抓新闻出错:", e)
        await asyncio.sleep(interval)

KEEP_ALIVE_URLS = [
    "https://globalinternationalnews.onrender.com/",
    "https://globalnews-5ose.onrender.com/",
    "https://www.mychinesenews.my",
    "https://allmychinesenews.onrender.com/"
]

async def periodic_keep_alive(interval=300, retry_delay=60):
    while True:
        for url in KEEP_ALIVE_URLS:
            success = False
            attempts = 0
            while not success:
                try:
                    attempts += 1
                    await asyncio.get_event_loop().run_in_executor(None, lambda: requests.get(url, timeout=60))
                    print(f"[{datetime.now()}] keep-alive 成功: {url}")
                    success = True
                except Exception as e:
                    print(f"[{datetime.now()}] keep-alive 失败 (尝试 {attempts}): {url} 错误: {e}")
                    await asyncio.sleep(retry_delay)
        await asyncio.sleep(interval)

# -------------------------- 首页 --------------------------
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    news = get_all_news()
    return templates.TemplateResponse("main.html", {"request": request, "news": news, "year": datetime.now().year})

@app.get("/category/{category}", response_class=HTMLResponse)
async def category_page(request: Request, category: str = Path(...)):
    news = get_all_news_by_category(category, skip=0, limit=20)
    return templates.TemplateResponse("category.html", {"request": request, "news": news, "category": category, "year": datetime.now().year})

@app.get("/news/{news_id}", response_class=HTMLResponse)
async def news_detail(request: Request, news_id: int):
    news_item = get_news_by_id(news_id)
    if not news_item:
        return HTMLResponse(content="新闻不存在", status_code=404)

    category = news_item["category"]
    prev_news = get_prev_news(news_id, category)
    next_news = get_next_news(news_id, category)

    return templates.TemplateResponse(
        "detail.html",
        {
            "request": request,
            "news_item": news_item,
            "prev_news": prev_news,
            "next_news": next_news,
            "year": datetime.now().year,
        },
    )

# -------------------------- API --------------------------
@app.get("/api/news", response_class=JSONResponse)
async def api_news(category: str = "all", skip: int = 0, limit: int = 20):
    if category.lower() == "all":
        news = get_all_news(skip=skip, limit=limit)
    else:
        news = get_all_news_by_category(category, skip=skip, limit=limit)
    return {"news": news}

# -------------------------- 静态页 --------------------------
@app.get("/about", response_class=HTMLResponse)
async def about(request: Request):
    return templates.TemplateResponse("about.html", {"request": request})

@app.get("/contact", response_class=HTMLResponse)
async def contact(request: Request):
    return templates.TemplateResponse("contact.html", {"request": request})

@app.get("/privacy", response_class=HTMLResponse)
async def privacy(request: Request):
    return templates.TemplateResponse("privacy.html", {"request": request})

@app.get("/terms", response_class=HTMLResponse)
async def terms(request: Request):
    return templates.TemplateResponse("terms.html", {"request": request, "year": datetime.now().year})

@app.get("/disclaimer", response_class=HTMLResponse)
async def disclaimer(request: Request):
    return templates.TemplateResponse("disclaimer.html", {"request": request, "year": datetime.now().year})

@app.get("/ads.txt", response_class=PlainTextResponse)
async def ads_txt():
    return "google.com, pub-2460023182833054, DIRECT, f08c47fec0942fa0"

@app.get("/robots.txt", response_class=PlainTextResponse)
async def robots_txt():
    content = """User-agent: *
Disallow:

Sitemap: https://www.mychinesenews.my/sitemap.xml
"""
    return PlainTextResponse(content)

# -------------------------- 管理 --------------------------
@app.get("/admin", response_class=HTMLResponse)
async def admin_get(request: Request):
    return templates.TemplateResponse("admin.html", {"request": request})

@app.post("/admin")
def add_news(
    request: Request,
    title: str = Form(...),
    content: str = Form(...),
    image_url: str = Form(None),
    category: str = Form('all')
):
    news_id = insert_news(title, content, image_url, category)
    append_news_to_sitemap(news_id)  # 追加到 sitemap
    return RedirectResponse("/maintenance", status_code=303)

def append_news_to_sitemap(news_id: int):
    news_item = get_news_by_id(news_id)
    if not news_item:
        return

    url = f"https://www.mychinesenews.my/news/{news_item['id']}"
    lastmod = news_item['created_at'].strftime("%Y-%m-%dT%H:%M:%S+08:00")
    new_item = f"""
  <url>
    <loc>{url}</loc>
    <lastmod>{lastmod}</lastmod>
    <changefreq>daily</changefreq>
    <priority>0.8</priority>
  </url>"""

    # 读取现有 sitemap，插入到 </urlset> 前
    if os.path.exists(SITEMAP_PATH):
        with open(SITEMAP_PATH, "r", encoding="utf-8") as f:
            content = f.read()
        content = content.replace("</urlset>", new_item + "\n</urlset>")
        with open(SITEMAP_PATH, "w", encoding="utf-8") as f:
            f.write(content)

@app.get("/maintenance", response_class=HTMLResponse)
async def maintenance(request: Request):
    columns, rows = get_all_db()
    return templates.TemplateResponse("maintenance.html", {"request": request, "columns": columns, "rows": rows, "zip": zip})

@app.post("/update/{news_id}")
async def update(
    news_id: int,
    title: str = Form(...),
    content: str = Form(...),
    image_url: str = Form(None),
    category: str = Form('all')
):
    update_news(news_id, title, content, image_url, category)
    update_news_in_sitemap(news_id)  # 同步更新 sitemap
    return RedirectResponse("/maintenance", status_code=303)

def update_news_in_sitemap(news_id: int):
    news_item = get_news_by_id(news_id)
    if not news_item or not os.path.exists(SITEMAP_PATH):
        return

    url_to_update = f"https://www.mychinesenews.my/news/{news_id}"
    new_url_block = f"""
  <url>
    <loc>{url_to_update}</loc>
    <lastmod>{news_item['created_at'].strftime("%Y-%m-%dT%H:%M:%S+08:00")}</lastmod>
    <changefreq>daily</changefreq>
    <priority>0.8</priority>
  </url>"""

    with open(SITEMAP_PATH, "r", encoding="utf-8") as f:
        lines = f.readlines()

    new_lines = []
    skip_block = False
    for line in lines:
        if "<url>" in line and url_to_update in line:
            skip_block = True  # 跳过原来的 url block
            new_lines.append(new_url_block + "\n")  # 替换成新内容
            continue
        if skip_block and "</url>" in line:
            skip_block = False
            continue
        if not skip_block:
            new_lines.append(line)

    with open(SITEMAP_PATH, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

@app.post("/delete/{news_id}")
async def delete(news_id: int):
    delete_news(news_id)
    remove_news_from_sitemap(news_id)  # 同步删除 sitemap 中的新闻
    return RedirectResponse("/maintenance", status_code=303)

def remove_news_from_sitemap(news_id: int):
    url_to_remove = f"https://www.mychinesenews.my/news/{news_id}"
    if not os.path.exists(SITEMAP_PATH):
        return

    with open(SITEMAP_PATH, "r", encoding="utf-8") as f:
        lines = f.readlines()

    new_lines = []
    skip_block = False
    for line in lines:
        if "<url>" in line and url_to_remove in line:
            skip_block = True  # 从 <url> 开始跳过
            continue
        if skip_block and "</url>" in line:
            skip_block = False  # 跳过到 </url>，然后继续
            continue
        if not skip_block:
            new_lines.append(line)

    with open(SITEMAP_PATH, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

# -------------------------- 启动 Uvicorn --------------------------
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=True)
