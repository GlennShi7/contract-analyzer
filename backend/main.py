from fastapi import FastAPI, UploadFile, File
from pydantic import BaseModel
from openai import OpenAI
import shutil
import os
from parser import extract_text
from embedder import search_chunks

from chunker import chunk_text
from embedder import store_chunks

from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = OpenAI(
    api_key=os.environ["DEEPSEEK_API_KEY"],
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
                "content": f"请分析这段合同条款的风险项，尤其帮我注意隐形费用收取和退房后押金退还，扣除的部分：{request.text}"
            }
        ]
    )
    return {"result": response.choices[0].message.content}


@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    # 把上传的文件临时保存到本地
    temp_path = f"temp_{file.filename}"
    with open(temp_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    
    # 提取文本
    text = extract_text(temp_path)
        # 切块并存入向量库，供 /ask 检索
    chunks = chunk_text(text)
    store_chunks(chunks, doc_id=file.filename)
    
    # 删除临时文件
    os.remove(temp_path)
    
    return {
        "filename": file.filename,
        "preview": text[:200],
        "text": text
    }

class AskRequest(BaseModel):
    question: str

@app.post("/ask")
def ask(request: AskRequest):
    try:
        relevant_chunks = search_chunks(request.question, n_results=2)
        context = "\n".join(relevant_chunks)
        
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {
                    "role": "system",
                    "content": "你是一个合同分析助手。请根据提供的合同内容回答用户问题。如果合同内容里没有相关信息，就如实说明。"
                },
                {
                    "role": "user",
                    "content": f"合同相关内容：\n{context}\n\n用户问题：{request.question}"
                }
            ]
        )
        return {"answer": response.choices[0].message.content}
    except Exception as e:
        return {"error": str(e)}