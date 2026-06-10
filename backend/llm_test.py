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
            "content": """你是一名专业的中国劳动法顾问，帮助普通劳动者分析劳动合同中的风险条款。

分析时请参考以下法律依据：
- 《劳动合同法》第23、24条：竞业限制条款须同时支付补偿金，否则无效
- 竞业限制期限不得超过2年
- 违约金须合理，不得显失公平

输出格式：
1. 条款风险等级（高/中/低）
2. 风险说明（用普通人能理解的语言）
3. 该条款是否符合法律规定
4. 建议"""
        },
        {
            "role": "user",
            "content": "乙方工资由基本工资及绩效组成，绩效考核标准由甲方单方面制定及调整，乙方无异议权。发生劳动争议，乙方须先通过公司内部调解，不得直接申请劳动仲裁。"
        }
    ]
)

print(response.choices[0].message.content)