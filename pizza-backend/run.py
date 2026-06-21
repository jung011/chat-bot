"""로컬 실행 런처. 실행: python run.py"""
from __future__ import annotations

import os

import uvicorn

if __name__ == "__main__":
    port = int(os.getenv("PORT", "9201"))
    print(f"[pizza-backend] FastAPI on http://127.0.0.1:{port}", flush=True)
    uvicorn.run("app.main:app", host="127.0.0.1", port=port)
