from openai import OpenAI

client = OpenAI(
    api_key="sk-e6d586af2c474b8382f6ef742754c8a0",
    base_url="https://api.deepseek.com"
)

response = client.chat.completions.create(
    model="deepseek-chat",
    messages=[
        {
            "role": "system",
            "content": """甲方有权根据生产经营需要随时调整乙方工作岗位、
工作地点及薪资标准，乙方须无条件服从，
否则视为自动离职，不享有任何补偿。"""
        },
        {
            "role": "user",
            "content": "甲方有权根据生产经营需要随时调整乙方工作岗位、工作地点及薪资标准，乙方须无条件服从，否则视为自动离职，不享有任何补偿。"
        }
    ]
)

print(response.choices[0].message.content)