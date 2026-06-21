"""중앙 임베딩 서버 (FastAPI + fastembed).

모델을 한 곳에서만 로딩해 오케스트레이터·MCP 서버가 HTTP 로 호출한다.
→ 임베딩 일관성(backend/model/dim)이 구조적으로 보장되고, 클라이언트 이미지는
onnxruntime/모델 없이 가벼워진다. (HuggingFace TEI 같은 기성 서버로 대체 가능)
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel

MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
_state: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    from fastembed import TextEmbedding

    model = TextEmbedding(model_name=MODEL)
    _state["model"] = model
    _state["dim"] = len(list(model.embed(["x"]))[0])
    print(f"[embedding-server] loaded {MODEL} (dim={_state['dim']})", flush=True)
    yield


app = FastAPI(title="embedding-server", lifespan=lifespan)


class EmbedRequest(BaseModel):
    texts: list[str]


@app.get("/health")
def health():
    return {"status": "ok", "model": MODEL, "dim": _state.get("dim")}


@app.post("/embed")
def embed(req: EmbedRequest):
    """텍스트 배열 → 벡터 배열. 단일/배치 모두 지원."""
    vectors = [v.tolist() for v in _state["model"].embed(req.texts)]
    return {"vectors": vectors, "dim": _state["dim"], "model": MODEL}
