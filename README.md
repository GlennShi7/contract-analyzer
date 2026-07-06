# Contract Risk Analyzer 合同防踩坑工具

Ordinary people signing rental or employment contracts are often harmed by unfavorable clauses they don't fully understand. Even when the law protects them, lack of legal knowledge often prevents them from exercising their rights. This project focuses on parsing contracts and identifying risky clauses, helping users make informed decisions before signing and quickly find their rights after signing.

普通人在租房、求职等涉及合同的场景中，常常因为看不懂合同而被恶意条款坑害，造成物质和精神上的损失。即使法律本身保护他们，他们也往往因为缺乏法律知识而无从维权。本项目专注于解读合同、识别风险条款，帮助用户在签约前做出明智决策，在签约后快速找到自己的权利依据。

## Tech Stack 技术栈

Frontend 前端: React
Backend 后端: Python + FastAPI
LLM: DeepSeek API
RAG: Hand-written implementation (no LangChain) 手写实现（不使用LangChain）
Vector DB 向量数据库: ChromaDB
Embedding Model 向量模型: paraphrase-multilingual-MiniLM-L12-v2 (local)
PDF Parsing PDF解析: pdfplumber

## Current Progress 当前进度

### Backend 后端 (Complete 已完成)

- [x] FastAPI project setup 项目搭建
- [x] DeepSeek API integration, `/analyze` endpoint for contract risk analysis
- [x] `/upload` endpoint, PDF upload and text extraction PDF上传与文本提取
- [x] Text chunking with overlap 文本切块（带重叠）
- [x] ChromaDB vector storage 向量存储
- [x] Semantic search 语义检索
- [x] `/ask` RAG-based Q&A endpoint 基于RAG的问答接口
- [x] API key managed via environment variables 使用环境变量管理密钥

### Frontend 前端 (In Progress 开发中)

- [ ] React project setup 项目初始化
- [ ] File upload component 文件上传组件
- [ ] Risk report display 风险报告展示
- [ ] Q&A chat interface 问答界面

## Run Locally 本地运行

### 1. Backend Setup 后端配置

```bash
cd backend
python -m venv venv
source venv/Scripts/activate  # Windows Git Bash
pip install -r requirements.txt
```

### 2. Configure API Key 配置密钥

Create a `.env` file in the `backend` folder 在 backend 文件夹下创建 `.env` 文件:

```
DEEPSEEK_API_KEY=your_deepseek_api_key_here
```

Get your key from 从这里获取密钥: https://platform.deepseek.com

### 3. Run the Server 启动服务器

```bash
uvicorn main:app --reload
```

Open `http://127.0.0.1:8000/docs` to test the API 打开该地址测试接口。

## API Endpoints 接口

### GET /hello
Health check endpoint 健康检查接口。

### POST /analyze
Submit a contract clause for risk analysis 提交合同条款进行风险分析。

```json
{
  "text": "Tenant must apply for deposit refund within 90 days after move-out, or forfeit the deposit automatically."
}
```

### POST /upload
Upload a PDF file, returns filename and a 200-character text preview 上传PDF，返回文件名和前200字文本预览。

### POST /ask
Ask a question about the uploaded contract. The system retrieves relevant clauses via semantic search and answers based on them 就上传的合同提问，系统通过语义检索找到相关条款并据此回答。

```json
{
  "question": "When can I get my deposit back?"
}
```

## Architecture 架构

```
PDF Upload
   -> pdfplumber (text extraction)
   -> chunker (split into overlapping chunks)
   -> embedder (vectorize + store in ChromaDB)
   -> Two paths:
      [1] /analyze: whole contract -> LLM -> risk report
      [2] /ask: question -> semantic search -> relevant chunks + question -> LLM -> answer
```
