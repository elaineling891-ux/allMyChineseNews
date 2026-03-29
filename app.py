import asyncio
import os
from datetime import datetime
import requests

from fastapi import FastAPI, Request, Form, Path
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse, FileResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

# Importing your custom modules
from db import (
    get_all_news, init_db, get_news_by_id, insert_news, 
    update_news, delete_news, get_all_db, 
    get_all_news_by_category, get_prev_news, get_next_news
)

app = FastAPI()

# Setup templates and static files
templates = Jinja2Templates(directory="templates")

# Ensure static directory exists to avoid startup errors
if not os.path.exists("static"):
    os.makedirs("static")
app.mount("/static", StaticFiles(directory="static"), name="static")

SITEMAP_PATH = "sitemap.xml"

# -------------------------- 启动事件 --------------------------
@app.on_event("startup")
async def startup_event():
    init_db()
    init_sitemap()
    # Start background tasks
    asyncio.create_task(periodic_keep_alive(300))

# -------------------------- Sitemap Logic --------------------------
def init_sitemap():
    if os.path.exists(SITEMAP_PATH):
        return

    try:
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
    except Exception as e:
        print(f"Sitemap init error: {e}")

@app.get("/sitemap.xml", response_class=FileResponse)
async def sitemap_xml():
    return FileResponse(SITEMAP_PATH, media_type="application/xml")

# -------------------------- Background Tasks --------------------------

KEEP_ALIVE_URLS = [
    "https://globalinternationalnews.onrender.com/",
    "https://globalnews-5ose.onrender.com/",
    "https://www.mychinesenews.my",
    "https://allmychinesenews.onrender.com/"
]

async def periodic_keep_alive(interval=300):
    while True:
        for url in KEEP_ALIVE_URLS:
            try:
                await asyncio.get_event_loop().run_in_executor(None, lambda u=url: requests.get(u, timeout=30))
                print(f"[{datetime.now()}] keep-alive 成功: {url}")
            except Exception as e:
                print(f"[{datetime.now()}] keep-alive 失败: {url} 错误: {e}")
        await asyncio.sleep(interval)

# -------------------------- 核心路由 (Main Routes) --------------------------
@app.get("/")
async def home(request: Request):
    news = get_all_news()
    return templates.TemplateResponse(
        request=request,
        name="main.html",
        context={"news": news, "year": datetime.now().year}
    )

@app.get("/category/{category}", response_class=HTMLResponse)
async def category_page(request: Request, category: str = Path(...)):
    news = get_all_news_by_category(category, skip=0, limit=20)
    return templates.TemplateResponse(
        request=request,
        name="category.html",
        context={"news": news, "category": category, "year": datetime.now().year}
    )
    
@app.get("/news/{news_id}")
async def news_detail(request: Request, news_id: int):
    news_item = get_news_by_id(news_id)
    return templates.TemplateResponse(
    request=request,
    name="detail.html",
    context={
        "news_item": news_item,  # Change "item" to "news_item"
        "year": datetime.now().year
    }
)

# -------------------------- API --------------------------
@app.get("/api/news", response_class=JSONResponse)
async def api_news(category: str = "all", skip: int = 0, limit: int = 20):
    if category.lower() == "all":
        news = get_all_news(skip=skip, limit=limit)
    else:
        news = get_all_news_by_category(category, skip=skip, limit=limit)
    return {"news": news}

# -------------------------- 静态信息页 --------------------------
@app.get("/about", response_class=HTMLResponse)
async def about(request: Request):
    return templates.TemplateResponse(request=request, name="about.html", context={})

@app.get("/contact", response_class=HTMLResponse)
async def contact(request: Request):
    return templates.TemplateResponse(request=request, name="contact.html", context={})

@app.get("/privacy", response_class=HTMLResponse)
async def privacy(request: Request):
    return templates.TemplateResponse(request=request, name="privacy.html", context={})

@app.get("/terms", response_class=HTMLResponse)
async def terms(request: Request):
    return templates.TemplateResponse(request=request, name="terms.html", context={"year": datetime.now().year})

@app.get("/disclaimer", response_class=HTMLResponse)
async def disclaimer(request: Request):
    return templates.TemplateResponse(request=request, name="disclaimer.html", context={"year": datetime.now().year})

@app.get("/ads.txt", response_class=PlainTextResponse)
async def ads_txt():
    return "google.com, pub-2460023182833054, DIRECT, f08c47fec0942fa0"

@app.get("/robots.txt", response_class=PlainTextResponse)
async def robots_txt():
    content = "User-agent: *\nDisallow:\n\nSitemap: https://www.mychinesenews.my/sitemap.xml"
    return content

# -------------------------- 管理功能 (Admin) --------------------------
@app.get("/admin", response_class=HTMLResponse)
async def admin_get(request: Request):
    return templates.TemplateResponse(request=request, name="admin.html", context={})

@app.post("/admin")
def add_news(
    request: Request,
    title: str = Form(...),
    content: str = Form(...),
    image_url: str = Form(None),
    category: str = Form('all')
):
    news_id = insert_news(title, content, image_url, category)
    append_news_to_sitemap(news_id)
    return RedirectResponse("/maintenance", status_code=303)

@app.get("/maintenance", response_class=HTMLResponse)
async def maintenance(request: Request):
    columns, rows = get_all_db()
    return templates.TemplateResponse(
        request=request,
        name="maintenance.html",
        context={"columns": columns, "rows": rows}
    )

@app.post("/update/{news_id}")
async def update(
    news_id: int,
    title: str = Form(...),
    content: str = Form(...),
    image_url: str = Form(None),
    category: str = Form('all')
):
    update_news(news_id, title, content, image_url, category)
    # update_news_in_sitemap(news_id) logic here if needed
    return RedirectResponse("/maintenance", status_code=303)

@app.post("/delete/{news_id}")
async def delete(news_id: int):
    delete_news(news_id)
    return RedirectResponse("/maintenance", status_code=303)

@app.get("/test")
async def test(request: Request):
    news = get_all_news()
    return templates.TemplateResponse(
        request=request,
        name="main.html",
        context={"news": news, "year": datetime.now().year}
    )

# -------------------------- Helper Functions --------------------------
def append_news_to_sitemap(news_id: int):
    news_item = get_news_by_id(news_id)
    if not news_item or not os.path.exists(SITEMAP_PATH):
        return
    url = f"https://www.mychinesenews.my/news/{news_item['id']}"
    lastmod = news_item['created_at'].strftime("%Y-%m-%dT%H:%M:%S+08:00")
    new_item = f"\n  <url>\n    <loc>{url}</loc>\n    <lastmod>{lastmod}</lastmod>\n    <changefreq>daily</changefreq>\n    <priority>0.8</priority>\n  </url>"
    with open(SITEMAP_PATH, "r", encoding="utf-8") as f:
        content = f.read()
    content = content.replace("</urlset>", new_item + "\n</urlset>")
    with open(SITEMAP_PATH, "w", encoding="utf-8") as f:
        f.write(content)

# -------------------------- Server Start --------------------------
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=True)
