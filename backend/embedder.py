import os

import chromadb
from chromadb.utils import embedding_functions

# 用本地中文模型做embedding
embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="paraphrase-multilingual-MiniLM-L12-v2"
)

# 创建ChromaDB客户端（本地持久化存储）
client = chromadb.PersistentClient(path="./chroma_db")

def store_chunks(chunks: list[str], doc_id: str):
    # 为每份文档创建或获取一个collection
    collection = client.get_or_create_collection(
        name="contracts",
        embedding_function=embedding_fn
    )
    # 存入chunks，每个chunk一个唯一id
    collection.add(
        documents=chunks,
        ids=[f"{doc_id}_chunk_{i}" for i in range(len(chunks))]
    )
    return collection.count()