# Contract Risk Analyzer 合同防踩坑工具

Ordinary people signing rental or employment contracts are often harmed by unfavorable clauses they don't fully understand. Even when the law protects them, lack of legal knowledge often prevents them from exercising their rights. This project focuses on parsing contracts and identifying risky clauses, helping users make informed decisions before signing and quickly find their rights after signing.

普通人在租房、求职等涉及合同的场景中，常常因为看不懂合同而被恶意条款坑害，造成物质和精神上的损失。即使法律本身保护他们，他们也往往因为缺乏法律知识而无从维权。本项目专注于解读合同、识别风险条款，帮助用户在签约前做出明智决策，在签约后快速找到自己的权利依据。

## Tech Stack 技术栈

Frontend 前端: React
Backend 后端: Python + FastAPI
LLM: DeepSeek API
RAG: Hand-written implementation (no LangChain) 手写实现（不使用LangChain）
Vector DB 向量数据库: ChromaDB
PDF Parsing PDF解析: pdfplumber

## Current Progress 当前进度

- [x] FastAPI project setup 项目搭建
- [x] DeepSeek API integration, `/analyze` endpoint for contract risk analysis
- [x] `/upload` endpoint, PDF upload and text extraction
- [ ] Text chunking 文本切块
- [ ] ChromaDB vector storage 向量存储
- [ ] `/ask` semantic Q&A endpoint 语义问答接口
- [ ] React frontend 前端

## Run Locally 本地运行

```bash
cd backend
python -m venv venv
source venv/Scripts/activate  # Windows Git Bash
pip install -r requirements.txt
uvicorn main:app --reload
```

Open `http://127.0.0.1:8000/docs` to test the API.

## API Endpoints

### GET /hello
Health check endpoint.

### POST /analyze
Submit a contract clause for risk analysis.

```json
{
  "text": "Tenant must apply for deposit refund within 90 days after move-out, or forfeit the deposit automatically."
}
```

### POST /upload
Upload a PDF file, returns filename and a 200-character text preview.
