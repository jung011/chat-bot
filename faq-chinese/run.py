"""로컬 실행 런처. 실행: python run.py"""
from __future__ import annotations

import uvicorn

from app.config import settings

if __name__ == "__main__":
    print(f"[faq-{settings.company_id}] FastAPI+MCP on http://{settings.host}:{settings.port}/mcp", flush=True)
    uvicorn.run("app.main:app", host=settings.host, port=settings.port)
