import cohere

# 这里换成你自己的 Cohere API Key
API_KEY = "你的_COHERE_API_KEY"

co = cohere.Client(API_KEY)

def paraphrase_text(text):
    """
    调用 Cohere API 改写文本
    """
    try:
        response = co.generate(
            model="command-xlarge-nightly",  # 免费 plan 可以用
            prompt=f"请帮我改写下面的文本，保持意思不变，语言自然流畅：\n\n{text}\n\n改写：",
            max_tokens=500,
            temperature=0.7
        )
        return response.generations[0].text.strip()
    except Exception as e:
        print("Cohere 改写失败:", e)
        return text  # 如果失败，就返回原文
