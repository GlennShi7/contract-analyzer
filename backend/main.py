from fastapi import FastAPI

app = FastAPI()

@app.get("/hello")
def hello():
    return {"message": "合同防踩坑工具 API 启动成功 🎉"}