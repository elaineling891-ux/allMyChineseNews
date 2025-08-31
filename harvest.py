import requests
from bs4 import BeautifulSoup
from db import insert_news, news_exists
import time
from urllib.parse import urljoin
from deep_translator import GoogleTranslator
import re

# --------------------------
# 初始化 Cohere 改写 API
# --------------------------
OPENAI_API_KEY = "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"
COHERE_URL = "https://api.cohere.ai/v1/chat"

def rewrite_text_chatgpt(text: str):
    """
    改写文本，自动处理长文本分段，失败自动重试
    """
    chunks = [text[i:i+MAX_TOKENS_PER_REQUEST] for i in range(0, len(text), MAX_TOKENS_PER_REQUEST)]
    rewritten = ""

    for chunk in chunks:
        for attempt in range(3):  # 最多重试 3 次
            try:
                url = "https://api.openai.com/v1/chat/completions"
                headers = {
                    "Authorization": f"Bearer {OPENAI_API_KEY}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": "gpt-3.5-turbo",
                    "messages": [
                        {"role": "system", "content": "你是中文写作助手。"},
                        {"role": "user", "content": f"请用中文改写以下文本，保持原意但用不同措辞：\n\n{chunk}"}
                    ],
                    "temperature": 0.7
                }
                resp = requests.post(url, headers=headers, json=payload, timeout=20)
                if resp.status_code != 200:
                    print(f"ChatGPT 请求失败 {resp.status_code}，重试 {attempt+1}/3")
                    time.sleep(2)
                    continue
                data = resp.json()
                rewritten += data["choices"][0]["message"]["content"].strip() + "\n"
                break
            except Exception as e:
                print(f"异常 {e}，重试 {attempt+1}/3")
                time.sleep(2)
        else:
            print("⚠️ 改写失败，保留原文本")
            rewritten += chunk + "\n"
    return rewritten.strip()

# --------------------------
# 后处理：添加换行，每3句换一次行
# --------------------------
def add_linebreaks(text, n_sentences=3):
    import re
    sentences = re.split(r'(?<=[。！？.!?])', text)
    lines = []
    for i in range(0, len(sentences), n_sentences):
        lines.append("".join(sentences[i:i+n_sentences]))
    return "\n\n".join(lines)

# --------------------------
# 翻译成简体中文
# --------------------------
def translate_to_simplified(text: str) -> str:
    try:
        return GoogleTranslator(source="auto", target="zh-CN").translate(text)
    except Exception as e:
        print("翻译失败:", e)
        return text

def rewrite_text(text):
    ok, rewritten = rewrite_text_chatgpt(text)
    if not ok:  # ❌ Cohere 失败
        return None

    rewritten = add_linebreaks(rewritten)
    rewritten = translate_to_simplified(rewritten)
    time.sleep(61)  # ✅ 每次调用后强制等待 61 秒
    return rewritten


# --------------------------
# 以下抓取文章内容、图片、网站新闻等保持不变
# --------------------------
def fetch_article_content(link):
    if not link:
        return ""
    try:
        resp = requests.get(link, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")

        if "udn.com" in link:
           div = (
                soup.select_one("section.article-content__editor")
                or soup.select_one("div.article-content__editor")
                or soup.select_one("div#article_body")
                or soup.select_one("div#story_body_content")  # 兜底旧版
            )
        elif "ltn.com" in link:
            div = (
                soup.select_one("div.text")
                or soup.select_one("div.cont")
                or soup.select_one("div#newsContent")
            )
        elif "yahoo.com" in link:
            div = soup.select_one("article")
        else:
            div = None

        if div:
            paragraphs = div.find_all("p")
            content = "\n".join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))
            return content
    except Exception as e:
        print(f"抓文章内容失败 ({link}): {e}")
    return ""

def fetch_article_image(link):
    if not link:
        return None
    try:
        resp = requests.get(link, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")
        img_url = None

        if "udn.com" in link:
             # ✅ 先抓 og:image / twitter:image
            meta = soup.select_one('meta[property="og:image"]') or soup.select_one('meta[name="twitter:image"]')
            if meta:
                img_url = meta.get("content")

            # 如果 meta 没有，再退回正文
            if not img_url:
                div = (
                    soup.select_one("div#story_body_content")
                    or soup.select_one("section.article-content__editor")
                )
                if div:
                    img = div.find("img")
                    if img:
                        img_url = img.get("data-src") or img.get("src")
           
        elif "ltn.com" in link:
            div = soup.select_one("div.text")
            if div:
                img = div.find("img")
                if img:
                    img_url = img.get("src")
        elif "yahoo.com" in link:
            meta = soup.select_one('meta[property="og:image"]')
            if meta:
                img_url = meta.get("content")

        if img_url and img_url.startswith("/"):
            img_url = urljoin(link, img_url)

        return img_url
    except Exception as e:
        print(f"抓文章图片失败 ({link}): {e}")
    return None

def fetch_site_news(url, limit=20):
    news_items = []
    try:
        resp = requests.get(url, timeout=20)
        soup = BeautifulSoup(resp.text, "html.parser")

        if "udn.com" in url:
            items = soup.select("div.story-list__text a")
        elif "ltn.com" in url:
            # LTN 首页和 breakingnews 页用这个 selector 就能抓到新闻链接
            items = soup.select("ul.list a")
        elif "yahoo.com" in url:
            items = soup.select("a[href*='/news/']")
        else:
            items = []

        for item in items[:limit]:
            title = item.get_text(strip=True)
            link = item.get("href")
            if link and link.startswith("/"):
                link = urljoin(url, link)

            # ✅ 针对 Yahoo：进入详情页抓真正标题
            if "yahoo.com" in url and link and link.startswith("http"):
                try:
                    article_res = requests.get(link, timeout=10)
                    article_soup = BeautifulSoup(article_res.text, "html.parser")

                    h1 = article_soup.select_one("h1")
                    if h1:
                        title = h1.get_text(strip=True)
                    else:
                        og_title = article_soup.select_one("meta[property='og:title']")
                        if og_title and og_title.get("content"):
                            title = og_title["content"].strip()
                        elif article_soup.title:
                            title = article_soup.title.string.strip()

                except Exception as e:
                    print(f"Yahoo 抓文章标题失败: {e}")

            # ✅ 针对 UDN：进入详情页抓真正标题
            elif "udn.com" in url and link and link.startswith("http"):
                try:
                    article_res = requests.get(link, timeout=10)
                    article_soup = BeautifulSoup(article_res.text, "html.parser")

                    h1 = article_soup.select_one("h1")
                    if h1:
                        title = h1.get_text(strip=True)
                    else:
                        og_title = article_soup.select_one("meta[property='og:title']")
                        if og_title and og_title.get("content"):
                            title = og_title["content"].strip()
                        elif article_soup.title:
                            title = article_soup.title.string.strip()

                except Exception as e:
                    print(f"UDN 抓文章标题失败: {e}")

            news_items.append((title, link))

    except Exception as e:
        print(f"抓 {url} 出错: {e}")
    return news_items

def fetch_news():
    all_news = []
    sites = [
        "https://udn.com/news/index",
        "https://news.ltn.com.tw/list/breakingnews",
        "https://tw.news.yahoo.com/"
    ]

    for url in sites:
        print(f"\n🌍 正在抓取站点: {url}")
        site_news = fetch_site_news(url, limit=20)

        if not site_news:
            print(f"⚠️ {url} 没有抓到新闻")
            continue

        for title, link in site_news:
            if not link:
                print(f"❌ 跳过：标题 [{title}] 没有链接")
                continue
            if news_exists(link):
                print(f"⏩ 已存在: {link}")
                continue
            if not title or title.strip() == "":
                print(f"❌ 跳过：空标题 (link={link})")
                continue

            content = fetch_article_content(link)
            if not content:
                print(f"❌ 跳过：[{title}] 没有正文内容")
                continue

            image_url = fetch_article_image(link)

            try:
                # ---------- 改写标题 ----------
                title_rw = rewrite_text(title)
                if not title_rw or title_rw.strip() == "":
                    print(f"❌ 改写标题失败，跳过 (link={link})")
                    continue

                # ---------- 改写正文 ----------
                content_rw = rewrite_text(content)
                if not content_rw or content_rw.strip() == "":
                    print(f"❌ 改写正文失败，跳过 (link={link})")
                    continue

                # ---------- 后处理 ----------
                title_rw = remove_comma_after_punct(title_rw)
                title_rw = dedup_sentences(title_rw)
                content_rw = remove_comma_after_punct(content_rw)
                content_rw = dedup_sentences(content_rw)

                # ---------- 入库 ----------
                insert_news(title_rw, content_rw, link, image_url)

                all_news.append({
                    "title": title_rw,
                    "content": content_rw,
                    "link": link,
                    "image_url": image_url
                })

                print(f"✅ 成功: {title_rw[:30]}... (link={link})")

            except Exception as e:
                print(f"❌ 插入失败: {title[:30]}... 错误: {e}")

    print(f"\n📊 本次共成功保存 {len(all_news)} 条新闻")
    return all_news

def remove_comma_after_punct(title: str) -> str:
    # 替换句号、感叹号、问号后面紧跟的中英文逗号
    title = re.sub(r'([。！？])[,，]+', r'\1', title)
    return title

def dedup_sentences(text: str) -> str:
    # 分句，保留标点
    parts = re.split(r'([。！？])', text)
    sentences = []
    for i in range(0, len(parts)-1, 2):
        sentence = parts[i].strip()
        punct = parts[i+1]
        full_sentence = sentence + punct
        sentences.append(full_sentence)

    result = []
    for s in sentences:
        if not result:
            result.append(s)
        else:
            prev = result[-1]
            # 1. 完全相同，跳过
            if prev == s:
                continue
            # 2. 如果当前句是前一句的尾部重复，也跳过
            elif prev.endswith(s):
                continue
            else:
                result.append(s)

    return "".join(result)


