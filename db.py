import asyncio
import os
from datetime import datetime
import functools
import requests

from fastapi import FastAPI, Request, Form, Path
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse, FileResponse
from fastapi.templating import Jinja2Templates

from db import (
    get_all_news,
    init_db,
    get_news_by_id,
    insert_news,
    update_news,
    delete_news,
    get_all_db,
    get_all_news_by_category,
    get_prev_news,
    get_next_news
)
from harvest import fetch_news

app = FastAPI()
templates = Jinja2Templates(directory="templates")

SITEMAP_PATH = "sitemap.xml"
KEEP_ALIVE_URLS = [
    "https://globalinternationalnews.onrender.com/",
    "https://globalnews-5ose.onrender.com/",
    "https://www.mychinesenews.my",
    "https://allmychinesenews.onrender.com/"
]

# -------------------------- Async Helpers --------------------------
async def run_blocking(func, *args, **kwargs):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, functools.partial(func, *args, **kwargs))

async def read_file_async(path):
    return await run_blocking(lambda: open(path, "r", encoding="utf-8").read())

async def write_file_async(path, content):
    await run_blocking(lambda: open(path, "w", encoding="utf-8").write(content))

async def fetch_url(url, timeout=60):
    await run_blocking(lambda: requests.get(url, timeout=timeout))

# -------------------------- Startup --------------------------
@app.on_event("startup")
async def startup_event():
    await run_blocking(init_db)
    await run_blocking(init_sitemap)
    asyncio.create_task(periodic_keep_alive(300))
    asyncio.create_task(periodic_fetch_news(43200))

# -------------------------- Sitemap --------------------------
def init_sitemap():
    if os.path.exists(SITEMAP_PATH):
        return
    columns, rows = get_all_db()
    idx_id = columns.index("id")
    idx_created = columns.index("created_at")
    sitemap_items = ""
    for row in rows:
        news_id = row[idx_id]
        created_at = row[idx_created]
        lastmod = created_at.strftime("%Y-%m-%dT%H:%M:%S+08:00") if hasattr(created_at, "strftime") else str(created_at)
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

async def append_news_to_sitemap(news_id: int):
    news_item = await run_blocking(get_news_by_id, news_id)
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
    if os.path.exists(SITEMAP_PATH):
        content = await read_file_async(SITEMAP_PATH)
        content = content.replace("</urlset>", new_item + "\n</urlset>")
        await write_file_async(SITEMAP_PATH, content)

async def update_news_in_sitemap(news_id: int):
    news_item = await run_blocking(get_news_by_id, news_id)
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
    content = await read_file_async(SITEMAP_PATH)
    lines = content.splitlines(keepends=True)
    new_lines = []
    skip_block = False
    for line in lines:
        if "<url>" in line and url_to_update in line:
            skip_block = True
            new_lines.append(new_url_block + "\n")
            continue
        if skip_block and "</url>" in line:
            skip_block = False
            continue
        if not skip_block:
            new_lines.append(line)
    await write_file_async(SITEMAP_PATH, "".join(new_lines))

async def remove_news_from_sitemap(news_id: int):
    url_to_remove = f"https://www.mychinesenews.my/news/{news_id}"
    if not os.path.exists(SITEMAP_PATH):
        return
    content = await read_file_async(SITEMAP_PATH)
    lines = content.splitlines(keepends=True)
    new_lines = []
    skip_block = False
    for line in lines:
        if "<url>" in line and url_to_remove in line:
            skip_block = True
            continue
        if skip_block and "</url>" in line:
            skip_block = False
            continue
        if not skip_block:
            new_lines.append(line)
    await write_file_async(SITEMAP_PATH, "".join(new_lines))

@app.get("/sitemap.xml", response_class=FileResponse)
async def sitemap_xml():
    return FileResponse(SITEMAP_PATH, media_type="application/xml")

# -------------------------- Periodic Tasks --------------------------
async def periodic_fetch_news(interval=43200):
    while True:
        try:
            print(f"⏳ [{datetime.now()}] 开始抓新闻...")
            await run_blocking(fetch_news)
            print(f"✅ [{datetime.now()}] 抓新闻完成")
        except Exception as e:
            print("抓新闻出错:", e)
        await asyncio.sleep(interval)

async def periodic_keep_alive(interval=300, retry_delay=60):
    while True:
        for url in KEEP_ALIVE_URLS:
            success = False
            attempts = 0
            while not success:
                try:
                    attempts += 1
                    await fetch_url(url)
                    print(f"[{datetime.now()}] keep-alive 成功: {url}")
                    success = True
                except Exception as e:
                    print(f"[{datetime.now()}] keep-alive 失败 (尝试 {attempts}): {url} 错误: {e}")
                    await asyncio.sleep(retry_delay)
        await asyncio.sleep(interval)

# -------------------------- Routes --------------------------
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    try:
        news = await run_blocking(get_all_news)
        return templates.TemplateResponse("main.html", {"request": request, "news": news, "year": datetime.now().year})
    except Exception as e:
        print("首页加载失败:", e)
        return HTMLResponse("服务器错误", status_code=500)

@app.get("/category/{category}", response_class=HTMLResponse)
async def category_page(request: Request, category: str = Path(...)):
    try:
        news = await run_blocking(get_all_news_by_category, category, 0, 20)
        return templates.TemplateResponse("category.html", {"request": request, "news": news, "category": category, "year": datetime.now().year})
    except Exception as e:
        print("分类页加载失败:", e)
        return HTMLResponse("服务器错误", status_code=500)

@app.get("/news/{news_id}", response_class=HTMLResponse)
async def news_detail(request: Request, news_id: int):
    try:
        news_item = await run_blocking(get_news_by_id, news_id)
        if not news_item:
            return HTMLResponse("新闻不存在", status_code=404)
        category = news_item["category"]
        prev_news = await run_blocking(get_prev_news, news_id, category)
        next_news = await run_blocking(get_next_news, news_id, category)
        return templates.TemplateResponse(
            "detail.html",
            {"request": request, "news_item": news_item, "prev_news": prev_news, "next_news": next_news, "year": datetime.now().year}
        )
    except Exception as e:
        print("新闻详情加载失败:", e)
        return HTMLResponse("服务器错误", status_code=500)

# -------------------------- API --------------------------
@app.get("/api/news", response_class=JSONResponse)
async def api_news(category: str = "all", skip: int = 0, limit: int = 20):
    try:
        if category.lower() == "all":
            news = await run_blocking(get_all_news, skip=skip, limit=limit)
        else:
            news = await run_blocking(get_all_news_by_category, category, skip, limit)
        return {"news": news}
    except Exception as e:
        print("API 获取新闻失败:", e)
        return JSONResponse({"error": "服务器错误"}, status_code=500)

# -------------------------- Static Pages --------------------------
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
    return f"""User-agent: *
Disallow:

Sitemap: https://www.mychinesenews.my/sitemap.xml
"""

# -------------------------- Admin --------------------------
@app.get("/admin", response_class=HTMLResponse)
async def admin_get(request: Request):
    return templates.TemplateResponse("admin.html", {"request": request})

@app.post("/admin")
async def add_news(
    request: Request,
    title: str = Form(...),
    content: str = Form(...),
    image_url: str = Form(None),
    category: str = Form('all')
):
    try:
        news_id = await run_blocking(insert_news, title, content, image_url, category)
        await append_news_to_sitemap(news_id)
        return RedirectResponse("/maintenance", status_code=303)
    except Exception as e:
        print("添加新闻失败:", e)
        return HTMLResponse("服务器错误", status_code=500)

@app.get("/maintenance", response_class=HTMLResponse)
async def maintenance(request: Request):
    try:
        columns, rows = await run_blocking(get_all_db)
        return templates.TemplateResponse("maintenance.html", {"request": request, "columns": columns, "rows": rows, "zip": zip})
    except Exception as e:
        print("维护页加载失败:", e)
        return HTMLResponse("服务器错误", status_code=500)

@app.post("/update/{news_id}")
async def update(
    news_id: int,
    title: str = Form(...),
    content: str = Form(...),
    image_url: str = Form(None),
    category: str = Form('all')
):
    try:
        await run_blocking(update_news, news_id, title, content, image_url, category)
        await update_news_in_sitemap(news_id)
        return RedirectResponse("/maintenance", status_code=303)
    except Exception as e:
        print("更新新闻失败:", e)
        return HTMLResponse("服务器错误", status_code=500)

@app.post("/delete/{news_id}")
async def delete(news_id: int):
    try:
        await run_blocking(delete_news, news_id)
        await remove_news_from_sitemap(news_id)
        return RedirectResponse("/maintenance", status_code=303)
    except Exception as e:
        print("删除新闻失败:", e)
        return HTMLResponse("服务器错误", status_code=500)

# -------------------------- Uvicorn --------------------------
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=True)
