from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict
from dotenv import load_dotenv
import os, json, uuid, faiss, numpy as np
from openai import OpenAI

# ---------- load API key ----------
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("Set OPENAI_API_KEY in .env or environment variables")

client = OpenAI(api_key=OPENAI_API_KEY)

MODEL_EMBED = "text-embedding-3-small"
MODEL_CHAT  = "gpt-4o-mini"
DATA_PATH   = "faiss_store"
os.makedirs(DATA_PATH, exist_ok=True)

# ---------- globals ----------
sessions: Dict[str, List[Dict[str, str]]] = {}
_index = None
doc_store: List[Dict[str, str]] = []
EMBED_DIM = 1536
HISTORY_TURNS = 8

app = FastAPI(title="Fintech Conversational Agent")

# ---------- helpers ----------
def ensure_index():
    global _index
    if _index is None:
        index_file = os.path.join(DATA_PATH, "faiss_index.bin")
        if os.path.exists(index_file):
            _index = faiss.read_index(index_file)
        else:
            _index = faiss.IndexFlatL2(EMBED_DIM)
    return _index

def get_embeddings(texts: List[str]) -> np.ndarray:
    res = client.embeddings.create(model=MODEL_EMBED, input=texts)
    vecs = [d.embedding for d in res.data]
    return np.array(vecs, dtype="float32")

def save_faiss():
    faiss.write_index(_index, os.path.join(DATA_PATH, "faiss_index.bin"))
    with open(os.path.join(DATA_PATH, "metadata.json"), "w", encoding="utf-8") as f:
        json.dump(doc_store, f, ensure_ascii=False, indent=2)

def load_faiss():
    global _index, doc_store
    index_file = os.path.join(DATA_PATH, "faiss_index.bin")
    meta_file  = os.path.join(DATA_PATH, "metadata.json")
    if os.path.exists(index_file):
        _index = faiss.read_index(index_file)
    else:
        _index = faiss.IndexFlatL2(EMBED_DIM)
    if os.path.exists(meta_file):
        with open(meta_file, "r", encoding="utf-8") as f:
            doc_store = json.load(f)

load_faiss()

# ---------- models ----------
class IngestRequest(BaseModel):
    content: str
    metadata: Optional[dict] = {}

class AskRequest(BaseModel):
    query: str
    session_id: Optional[str] = None
    allow_tools: bool = True
    top_k: int = 4

# ---------- endpoints ----------
@app.post("/ingest")
def ingest(req: IngestRequest):
    vecs = get_embeddings([req.content])
    index = ensure_index()
    index.add(vecs)
    doc_store.append({"content": req.content, "metadata": req.metadata})
    save_faiss()
    return {"status": "indexed", "total_docs": len(doc_store)}

@app.post("/ask")
def ask(req: AskRequest):
    sid = req.session_id or str(uuid.uuid4())
    sessions.setdefault(sid, [])

    # append user msg
    sessions[sid].append({"role": "user", "content": req.query})

    # retrieve context
    ctx_docs = []
    if req.allow_tools and len(doc_store) > 0:
        qv = get_embeddings([req.query])
        D, I = _index.search(qv, req.top_k)
        for idx in I[0]:
            if 0 <= idx < len(doc_store):
                ctx_docs.append(doc_store[idx]["content"])

    # build prompt with history
    recent = sessions[sid][-HISTORY_TURNS:]
    messages = [
        {"role": "system", "content": "You are a helpful Fintech assistant. Use context + chat history."}
    ]
    messages.extend(recent)
    if ctx_docs:
        messages.append({"role": "system",
                         "content": "Context:\n" + "\n---\n".join(ctx_docs)})

    resp = client.chat.completions.create(model=MODEL_CHAT, messages=messages)
    answer = resp.choices[0].message.content

    sessions[sid].append({"role": "assistant", "content": answer})
    return {"session_id": sid, "answer": answer, "context_docs_used": len(ctx_docs)}

@app.get("/")
def root():
    return {"status": "Fintech agent backend running"}
