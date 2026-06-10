from fastapi import FastAPI, UploadFile, File
from pydantic import BaseModel
from openai import OpenAI

app = FastAPI()

client = OpenAI(
    api_key="sk-e6d586af2c474b8382f6ef742754c8a0",
    base_url="https://api.deepseek.com"
)

class ContractRequest(BaseModel):
    text: str

@app.get("/hello")
def hello():
    return {"message": "合同防踩坑工具 API 启动成功 🎉"}

@app.post("/analyze")
def analyze(request: ContractRequest):
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {
                "role": "system",
                "content": "你是一个专业的合同分析助手，帮助普通用户识别合同中的风险条款，用简单易懂的语言解释。"
            },
            {
                "role": "user",
                "content": f"请分析这段合同条款的风险：{request.text}"
            }
        ]
    )
    return {"result": response.choices[0].message.content}


@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    return {"filename": file.filename}