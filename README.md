
# 自动华语新闻（Flask + PostgreSQL）

- 修改 `sources.json` 即可调整/新增抓取源（基于 CSS selector）
- `/` 首页展示数据库最新标题
- `/fetch` 触发抓取（可用 cron-job.org 定时访问）
- 启动时自动建表 `news`

## 本地运行
```bash
python -m venv venv
source venv/bin/activate  # Windows 用 venv\Scripts\activate
pip install -r requirements.txt
export DATABASE_URL=postgres://USER:PASS@HOST:5432/DB
python app.py
# 访问 http://127.0.0.1:5000 ，手动触发 http://127.0.0.1:5000/fetch
```

## Render 部署
- Build Command：`pip install -r requirements.txt`
- Start Command：`gunicorn app:app`
- 环境变量：`DATABASE_URL`（填你的 PostgreSQL 连接串，如 Neon/Supabase/Render PG）
- Python 版本：由 `runtime.txt` 指定为 3.11.9

## 定时抓取（无 Cron 权限时）
使用 cron-job.org 新建任务，URL 指向：`https://你的域名/fetch`，建议每 30-60 分钟执行一次。

## AdSense
在 `templates/index.html` 中把 `ca-pub-xxxxxxxx` 和 `data-ad-slot` 替换为你的值。

> 合规提示：本站仅保存“标题 + 原文链接 + 来源”，不存储全文内容，点击后跳转原站，降低版权风险。
