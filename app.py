import asyncio
import os
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from db import init_db, insert_news, update_news, delete_news, get_all_db, get_news_by_id
from datetime import datetime
import requests

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# -------------------------- 启动 --------------------------
@app.on_event("startup")
async def startup_event():
    init_db()
    asyncio.create_task(periodic_keep_alive(300))

KEEP_ALIVE_URLS = [
    "https://globalinternationalnews.onrender.com/",
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

# -------------------------- 管理 --------------------------
@app.get("/maintenance", response_class=HTMLResponse)
async def maintenance(request: Request):
    columns, rows = get_all_db()
    return templates.TemplateResponse("maintenance.html", {"request": request, "columns": columns, "rows": rows, "zip": zip})

@app.post("/admin")
async def add_news_api(title: str = Form(...), content: str = Form(...), link: str = Form(None), image_url: str = Form(None)):
    insert_news(title, content, link, image_url)
    columns, rows = get_all_db()
    news_list = [dict(zip(columns, row)) for row in rows]
    return JSONResponse({"message": "✅ 新闻已成功提交！", "news": news_list})

@app.post("/update/{news_id}")
async def update_news_api(news_id: int, title: str = Form(...), content: str = Form(...), link: str = Form(None), image_url: str = Form(None)):
    update_news(news_id, title, content, link, image_url)
    news_item = get_news_by_id(news_id)
    return JSONResponse({"message": "✅ 更新成功", "news_item": news_item})

@app.post("/delete/{news_id}")
async def delete_news_api(news_id: int):
    delete_news(news_id)
    return JSONResponse({"message": "✅ 删除成功", "news_id": news_id})

# -------------------------- 启动 --------------------------
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=True)
