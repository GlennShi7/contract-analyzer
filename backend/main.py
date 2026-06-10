from fastapi import FastAPI, UploadFile, File
from pydantic import BaseModel

app = FastAPI()

class ContractRequest(BaseModel):
    text: str

@app.get("/hello")
def hello():
    return {"message": "合同防踩坑工具 API 启动成功 🎉"}

@app.post("/analyze")
def analyze(request: ContractRequest):
    return {"received": request.text}

@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    return {"filename": file.filename}