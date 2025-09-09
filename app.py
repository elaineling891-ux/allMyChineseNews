import asyncio
import os
from fastapi import FastAPI, Request, Form, Path
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from db import get_all_news, init_db, get_news_by_id, insert_news, update_news, delete_news, get_all_db, get_all_news_by_category
from harvest import fetch_news
from datetime import datetime
import requests

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# -------------------------- 启动事件 --------------------------
@app.on_event("startup")
async def startup_event():
    init_db()
    asyncio.create_task(periodic_keep_alive(300))

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
    "https://www.mychinesenews.my"
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
    return templates.TemplateResponse("detail.html", {"request": request, "news_item": news_item, "year": datetime.now().year})

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

# -------------------------- 管理 --------------------------
@app.get("/admin", response_class=HTMLResponse)
async def admin_get(request: Request):
    return templates.TemplateResponse("admin.html", {"request": request})

@app.post("/admin")
def add_news(
    request: Request,
    title: str = Form(...),
    content: str = Form(...),
    link: str = Form(None),
    image_url: str = Form(None),
    category: str = Form('all')
):
    insert_news(title, content, link, image_url, category)
    return RedirectResponse("/maintenance", status_code=303)

@app.get("/maintenance", response_class=HTMLResponse)
async def maintenance(request: Request):
    columns, rows = get_all_db()
    return templates.TemplateResponse("maintenance.html", {"request": request, "columns": columns, "rows": rows, "zip": zip})

@app.post("/update/{news_id}")
async def update(
    news_id: int,
    title: str = Form(...),
    content: str = Form(...),
    link: str = Form(None),
    image_url: str = Form(None),
    category: str = Form('all')
):
    update_news(news_id, title, content, link, image_url, category)
    return RedirectResponse("/maintenance", status_code=303)

@app.post("/delete/{news_id}")
async def delete(news_id: int):
    delete_news(news_id)
    return RedirectResponse("/maintenance", status_code=303)

# -------------------------- 启动 Uvicorn --------------------------
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=True)
