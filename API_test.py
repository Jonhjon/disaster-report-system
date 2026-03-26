import anthropic
import os

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

message = client.messages.create(
    # model="claude-haiku-4-5-20251001", # 模型型號
    model="claude-sonnet-4-6",
    max_tokens=1000, # 選用，回傳token的最大長度，避免爆預算
    messages=[
        {"role": "user", "content": "test"}
    ]
)

print(message.content)

# from google import genai

# api_key = os.environ.get("GOOGLE_API_KEY")
# client = genai.Client(api_key=api_key)

# # 改用 gemini-2.0-flash-lite，免費配額較寬鬆
# response = client.models.generate_content(
#     model="gemini-2.0-flash-lite",
#     contents="用一句話介紹你自己"
# )

# print("\n回答:")
# print(response.text)