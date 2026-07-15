"""獨立的 eval FastAPI app — 只跑 LLM 萃取路徑，供 eval harness 使用。

啟動方式（在 backend/ 目錄下）：
    venv\\Scripts\\python.exe -m uvicorn eval_server:app --port 8002

這支 app 與正式 `app.main:app` 完全獨立：
- 不 mount 正式的 chat / events / reports 路由。
- 沒有 CORS、沒有靜態檔、沒有 lifespan 背景任務。
- 唯一 endpoint：POST /eval/chat，內部沿用 `app.services.llm_service.stream_chat`，
  跟正式流程共用萃取邏輯（SYSTEM_PROMPT / SUBMIT_TOOL / model / stream），
  但不做 geocoding / dedup / DB / broker。

用途：跑 Suite G / 其他純 LLM 萃取類 suite 時，harness 打 8002 這支 app，
確保 assertion 檢查的是 LLM 原始輸出，不會被 backend 的後處理污染。

Endpoint 路徑刻意沿用正式 backend 的 `/api/chat` —— harness 的 conversation.py 是
寫死這條 URL；用同 path 但不同 port 是最乾淨的分離方式（8001 = prod，8002 = eval）。
"""
from __future__ import annotations

from fastapi import FastAPI

from app.api import eval_chat

app = FastAPI(title="災害通報系統 Eval Server", version="1.0.0")
app.include_router(eval_chat.router, prefix="/api", tags=["Eval"])


@app.get("/")
def root():
    return {"message": "eval server — POST /api/chat (LLM-only, no postprocess)"}
