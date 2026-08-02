# 合同防踩坑工具 —— 项目交接文档

> 本文档用于向 Claude Code / Codex 交接项目上下文。
> 最后更新：2026-08-01

---

## 一、项目定位

### 一句话描述
面向中文用户的合同风险分析工具。用户上传租房合同、劳动合同等 PDF，AI 自动识别风险条款、给出风险评分，并支持针对合同内容的自然语言问答。

### 正式定位表述（可直接用于 README / 面试开场）
> 普通人在租房、求职等涉及合同的场景中，常常因为看不懂合同而被恶意条款坑害，造成物质和精神上的损失。即使法律本身保护他们，他们也往往因为缺乏法律知识而无从维权。"合同防踩坑工具"专注于解读合同、识别风险条款，帮助用户在签约前做出明智决策，在签约后快速找到自己的权利依据。

### 目标用户与场景
目标用户：没有法律背景的普通租客、求职者、个体工商户。

**关键产品洞察（经过讨论得出，面试时可讲）**：用户没有修改合同的议价能力，所以工具不做"生成反提议条款"这类功能。真实需求分两个场景：

| | 场景A | 场景B |
|---|---|---|
| 时机 | 签字前 | 签字后遇到纠纷 |
| 需求 | "我该不该签" | "我现在有什么权利" |
| 对应功能 | `/analyze` 风险识别+评分 | `/ask` RAG 语义问答 |

两个接口分工不同：analyze 保全面（整份合同喂给 LLM），ask 保精准（RAG 检索最相关片段）。这个设计本身缓解了 RAG 召回率不足的问题。

### 真实动机
开发者本人租房时险遭押金陷阱，发现大多数人无力支付律师费审合同。

---

## 二、技术栈

| 层 | 选型 | 决策理由 |
|---|---|---|
| 前端 | React (Vite) | 区别于同类项目常用的 Streamlit，体现真实全栈工程能力 |
| 后端 | Python + FastAPI | async 支持好，自动生成 API 文档方便调试 |
| LLM | DeepSeek API (`deepseek-chat`) | OpenAI 有地区限制无法注册；DeepSeek 便宜、中文强、API 格式与 OpenAI 兼容 |
| RAG | **手写实现，不用 LangChain** | 核心差异化：能完整解释 chunking 策略和 retrieval 逻辑 |
| 向量数据库 | ChromaDB (PersistentClient) | 本地部署，无需搭服务器，API 简单 |
| Embedding | `paraphrase-multilingual-MiniLM-L12-v2`（本地 sentence-transformers） | DeepSeek 无 embedding 接口，OpenAI 不可用；本地模型免费、无网络依赖、支持中文 |
| PDF 解析 | pdfplumber | |
| 密钥管理 | python-dotenv + `.env` | 曾发生 API key 泄露事故，见下文 |

---

## 三、当前进度

### 后端 —— 已全部完成 ✅

- [x] FastAPI 项目搭建
- [x] `GET /hello` 健康检查
- [x] `POST /analyze` 接收合同文字 → DeepSeek 分析 → 返回风险解读
- [x] `POST /upload` 上传 PDF → pdfplumber 提取文本 → 返回前 200 字预览
- [x] `chunker.py` 文本切块（chunk_size=500, overlap=50）
- [x] `embedder.py` 向量化 + ChromaDB 持久化存储
- [x] 语义检索 `search_chunks()`
- [x] `POST /ask` 完整 RAG 问答链路
- [x] API key 迁移到环境变量

### 前端 —— 刚起步 🚧

- [x] Node.js 已安装（node v26.5.1 / npm 11.17.0）
- [ ] **当前卡点：正准备执行 `npm create vite@latest frontend -- --template react`**
- [ ] Upload 组件（文件上传）
- [ ] RiskReport 组件（风险报告展示）
- [ ] QAChat 组件（问答界面）
- [ ] 前后端联调（需处理 CORS）

---

## 四、代码现状

### 目录结构
```
contract-analyzer/
├── README.md              # 双语，英文在前中文在后
├── backend/
│   ├── main.py            # FastAPI 入口，所有接口
│   ├── parser.py          # PDF 文本提取
│   ├── chunker.py         # 文本切块
│   ├── embedder.py        # 向量化 + ChromaDB 存取 + 语义检索
│   ├── requirements.txt
│   ├── .env               # DEEPSEEK_API_KEY（已 gitignore）
│   ├── .gitignore         # 含 venv/ __pycache__/ .env chroma_db/
│   ├── venv/
│   └── chroma_db/         # ChromaDB 本地持久化数据
└── frontend/              # 空，待初始化
```

### main.py 现状
```python
from fastapi import FastAPI, UploadFile, File
from pydantic import BaseModel
from openai import OpenAI
import shutil
import os
from parser import extract_text
from embedder import search_chunks
from dotenv import load_dotenv
load_dotenv()

app = FastAPI()

client = OpenAI(
    api_key=os.environ["DEEPSEEK_API_KEY"],
    base_url="https://api.deepseek.com"
)

class ContractRequest(BaseModel):
    text: str

class AskRequest(BaseModel):
    question: str

# GET  /hello    健康检查
# POST /analyze  接收 ContractRequest，调 DeepSeek 分析风险
# POST /upload   接收 PDF，存临时文件 → extract_text → 删临时文件 → 返回预览
# POST /ask      检索相关 chunks → 拼 context → 喂 LLM → 返回答案
#                目前带 try/except，异常时返回 {"error": str(e)}
```

### chunker.py
```python
def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks
```

### embedder.py
```python
import chromadb
from chromadb.utils import embedding_functions

embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="paraphrase-multilingual-MiniLM-L12-v2"
)
client = chromadb.PersistentClient(path="./chroma_db")

def store_chunks(chunks: list[str], doc_id: str): ...
def search_chunks(query: str, n_results: int = 3): ...
```

### parser.py
```python
import pdfplumber

def extract_text(file_path: str) -> str:
    text = ""
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            text += page.extract_text() or ""
    return text
```

---

## 五、⚠️ 重要事故记录：API Key 泄露

**发生了什么**：API key 曾硬编码在 `main.py` 里并 push 到 public GitHub repo，被爬虫扫描盗刷。用量面板显示 ¥10.13 花在 `deepseek-v4-flash` / `deepseek-v4-pro` 上（近 700 万 token），而项目代码用的是 `deepseek-chat`（花费 ¥0.00），可确认为盗用。

**已处置**：
1. 旧 key 已在 DeepSeek 平台禁用
2. 新 key 存于 `backend/.env`，已被 `.gitignore` 忽略
3. 代码改为 `os.environ["DEEPSEEK_API_KEY"]` + `load_dotenv()`

**遗留隐患**：旧 key 仍存在于 Git 提交历史中。因已禁用，风险可控，暂未清理历史（清理需 force push，有风险）。

**铁律**：任何密钥一律走 `.env`，绝不写进代码。push 前用 `git status` 确认 `.env` 不在待提交列表中。

---

## 六、环境与踩坑清单（重要，可节省大量调试时间）

### 环境
- **系统**：Windows
- **终端**：VSCode 内使用 **Git Bash**（不要用 PowerShell，语法不兼容，`source`、`mkdir a b`、`rm -rf` 等都会失败）
- **项目路径**：`C:/Users/ASUS/contract-analyzer`，Git Bash 中为 `/c/Users/ASUS/contract-analyzer`
- **激活 venv**：`cd backend && source venv/Scripts/activate`
- **启动后端**：`uvicorn main:app --reload`，测试地址 `http://127.0.0.1:8000/docs`

### 高频踩坑（这些坑已经踩过，别再踩）

1. **全角字符静默杀死代码** —— 中文输入法打出的全角空格/逗号混入 Python 代码，会导致整段代码静默失效（不报错、不执行）。多次发生在 `if __name__ == "__main__":` 测试块中。写代码务必切英文输入法。

2. **缩进错误导致测试代码进函数体** —— `if __name__` 块被误缩进到函数 `return` 之后，永远不执行。表现同样是"没输出也没报错"。

3. **不在正确目录** —— 反复出现在 `contract-analyzer` 根目录执行 `python chunker.py`，而文件在 `backend/` 下。运行前先 `pwd` 确认。

4. **venv 未激活** —— 表现为 `uvicorn: command not found` 或 `ModuleNotFoundError`。

5. **HuggingFace 模型下载**：
   - 挂 VPN 时：直连 HF，不要设 `HF_ENDPOINT` 镜像（会冲突报连不上）
   - 不挂 VPN 时：设 `os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"`
   - 模型 `shibing624/text2vec-base-chinese` 在镜像站缺权重文件，已弃用，改用 `paraphrase-multilingual-MiniLM-L12-v2`

6. **循环 import** —— 曾误在 `embedder.py` 里写 `from embedder import search_chunks`（自己 import 自己）。

7. **接口代码写错文件** —— 曾把 `/ask` 的 `class AskRequest(BaseModel)` 写进了 `embedder.py`，导致 `NameError: BaseModel is not defined`。

8. **FastAPI 文件上传需要额外依赖** —— `pip install python-multipart`，否则 `/upload` 报 RuntimeError。

9. **DeepSeek 余额** —— 余额不足时报 `Error code: 402 - Insufficient Balance`，表现为接口 500。曾因此误判为代码 bug 排查很久。

10. **Git 分支** —— 本地代码全部在 `master` 分支，但 GitHub repo 默认显示 `main` 分支（只有 `.gitignore` 和 `LICENSE`）。导致误以为 push 失败。**建议：GitHub Settings → Branches → 把默认分支改成 master**。

---

## 七、竞品调研结论（面试可用）

调研过 6 个同类项目，最直接的竞品是 **Lexis AI**：

| | Lexis AI | 本项目 |
|---|---|---|
| LLM | GPT-4o-mini | DeepSeek |
| 向量库 | FAISS | ChromaDB |
| RAG | **LangChain 封装** | **手写实现** ✅ |
| 前端 | Streamlit | **React** ✅ |
| 语言 | 多语言自动检测 | 中文专项 ✅ |
| 法规知识 | 无 | 计划加入中国法规 ✅ |

**值得借鉴的点**：
- Lexis AI 把所有 LLM 调用抽成一个私有 `_ask()` 方法复用，只换 prompt
- prompt 结尾强制要求 `Return ONLY a JSON array`，便于 `json.loads()` 解析
- 中文项目 zsc545758363/AI_ContractAnalysis 写了 `parse_json_with_code_blocks()` 清洗函数，处理 LLM 返回被 markdown 代码块包裹的问题——**做结构化输出时直接抄这个思路**
- 该项目还用 pdf2image + PaddleOCR 支持扫描件 PDF（本项目 pdfplumber 无法处理扫描件）

**核心壁垒**：手写 RAG × React 全栈 × 中文法规专项，这个组合目前未见有人做完。

---

## 八、剩余工作与时间线

**背景：原计划 7/20 完工，因支教和私事延误，现为 8/1，需压缩冲刺。8 月开始投简历。**

### 优先级排序（时间不够时从下往上砍）

**P0 —— 必须完成，否则无法演示**
1. Vite 初始化 React 项目
2. Upload 组件 + 调 `/upload` 接口
3. RiskReport 组件 + 调 `/analyze` 接口
4. 前后端联调，解决 CORS（FastAPI 需加 `CORSMiddleware`）

**P1 —— 强烈建议完成**
5. QAChat 组件 + 调 `/ask` 接口
6. `/analyze` 改为返回结构化 JSON（风险评分 + 条款列表 + 风险等级）
7. 前端按风险等级着色（高红 / 中黄 / 低绿）

**P2 —— 差异化亮点，有时间就做**
8. prompt 中注入中国劳动法/租房法规要点，让分析能引用具体法条
9. 合同类型自动识别（租房/劳动）
10. 错误处理健壮性（非 PDF、空文件、API 超时）

**P3 —— 可砍**
11. SQLite 历史记录
12. 部署上线
13. 扫描件 OCR 支持

### 明确不做
用户登录系统、云端存储、移动端适配、Docker 部署。

---

## 九、协作偏好（重要）

与本项目开发者协作时请注意：

- **语言**：中文技术讨论
- **讲解风格**：喜欢**逐行"句读"式讲解**代码，每行在干什么、为什么这么写。给完代码后主动解释，不要等他问
- **理解优先于复制**：明确表示要理解底层原理用于面试，不满足于跑通就行
- **格式偏好**：讨厌过度格式化、checkbox、冗余的计划排版。要简洁直给
- **调试习惯**：遇到报错先看最后一行 `XXXError`，不要被中间堆栈迷惑
- **LeetCode 部分**：希望先独立写出暴力解，然后要**逐条渐进式提示**，不要直接给答案；重视"什么时候用 dict / set / 单变量"这类模式识别框架
- **诚实反馈**：会直接指出 AI 的幻觉和错误判断（例如"你那能跑我这不能跑，那不就是问题所在吗"），需要就事论事、不要嘴硬也不要过度道歉

---

## 十、LeetCode 进度

已完成约 4-5 题：Two Sum、Best Time to Buy and Sell Stock、Contains Duplicate、Valid Anagram、3Sum（部分）。

目标：投简历前累计 35-40 题，覆盖 Array / String / HashMap / Tree 基础题型，中厂 Easy + 部分 Medium 水平。

已学 Array 基础知识：内存连续存储、O(1) 随机访问、常用技巧（双指针 / 滑动窗口 / HashMap 换时间 / 前缀和）。

---

## 十一、面试讲解要点（已积累的素材）

1. **为什么手写 RAG 不用 LangChain** —— 完整掌握 chunking 策略和 retrieval 逻辑，能解释每一步设计取舍
2. **chunking 策略** —— 固定步长滑动切割，chunk_size=500、overlap=50 防止关键信息在边界被切断
3. **RAG 召回率权衡** —— `n_results` 太小漏内容、太大引入噪音且 token 成本高；本项目用 analyze（全量）+ ask（检索）双路径分工缓解
4. **Embedding 选型** —— DeepSeek 无 embedding 接口，改用本地 sentence-transformers，保证零成本和本地可复现
5. **产品思考** —— 用户无议价能力，因此覆盖"签前识别风险 + 签后查询权利"双场景，而非生成谈判条款
6. **安全实践** —— 经历过 API key 泄露事故，现全部走环境变量管理
