# Retrieval evaluation 检索评测

Measures how often the `/ask` path retrieves the clause that answers a user's question.
衡量 `/ask` 的语义检索能否找到回答用户问题的那条条款。

```bash
cd backend
source venv/Scripts/activate          # Windows Git Bash
python -m pip install -r requirements-dev.txt
python -m eval.retrieval_eval          # defaults to top-3; /ask currently uses top-2
python -m eval.retrieval_eval --sweep  # also compare chunk sizes 对比不同切块大小
python -m pytest eval -q               # unit tests for the scoring 评分逻辑的单元测试
```

If the model download hangs, run with `HF_HUB_OFFLINE=1` (the model is already cached after the app has run once).
如果卡在下载模型，加 `HF_HUB_OFFLINE=1`（应用跑过一次后模型已在本地缓存）。

## What is measured 测什么

- The production code is used as is: `chunker.chunk_text` splits the contract and `embedder.embedding_fn`
  (paraphrase-multilingual-MiniLM-L12-v2) embeds it, into a throwaway in-memory Chroma collection.
  Evaluation documents are stored only in these temporary collections. Importing `embedder.py`
  also initializes its persistent `./chroma_db` client, so that directory may be created or initialized.
  评测合同只存入临时内存索引；导入 embedder 时仍会初始化持久化客户端。
- **hit@k**: one of the top k retrieved chunks covers at least half of the sentence that answers the
  question. The default k = 3 comes from `search_chunks`' signature; `/ask` explicitly passes 2.
  前 k 个结果里有一块覆盖了答案原句的一半以上；评测默认取 3 块，接口实际取 2 块。
- **random**: the hit rate of k chunks drawn at random. Bigger chunks cover more of the contract, so a
  hit rate means little without this baseline. 随机抽 k 块的命中率，作为基线。
- **model reads**: the embedding model reads at most 128 tokens per chunk and ignores the rest. This is
  the share of each chunk it actually sees. 模型每块最多读 128 个 token，这一栏是它实际读到的比例。
- **one collection**: `embedder.py` stores every upload in the same `contracts` collection and
  `search_chunks` does not filter by document, so with several contracts stored, chunks from other
  contracts come back. This run puts all three contracts in one collection and reports how often that
  happens. 所有合同存在同一个 collection 且检索时不按文档过滤，这一项测检索到别的合同的比例。

## Data 数据

- `contracts/`: three contracts written for this evaluation, modeled on the structure of public model
  contracts and on clauses common in practice, including unfair ones: a Chinese residential lease
  (租房合同), a Chinese employment contract (劳动合同) and an English residential lease for Urbana, IL.
  三份为评测编写的合同，参照公开示范文本的结构和实践中常见（包括不公平）的条款。
- `questions.jsonl`: 56 questions written the way users ask them, not copied from the clause text, each
  labeled with the sentence or sentences that answer it. 20 of them are about the English lease, half
  asked in English and half in Chinese (cross-lingual retrieval). 56 道按用户口吻写的问题，每题标注答案原句；
  英文租约的 20 题一半用英文问、一半用中文问。

Limitations 局限: plain text input, so PDF extraction is not part of the measurement; a small labeled set;
the contracts are not real signed contracts. 输入是纯文本，不含 PDF 解析；题量小；合同不是真实签过的合同。
