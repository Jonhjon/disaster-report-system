"""Eval-only chat endpoint — 純測 LLM 萃取，不做 postprocess。

此模組刻意與正式的 `app.api.chat` 完全分離：
- 不做 geocoding、dedup、DB 寫入、broker publish、verified_phone 覆寫。
- 直接把 `llm_service.stream_chat` yield 的原始 tool_use payload 透過 SSE 送出。
- 供 `backend/eval_server.py`（獨立 FastAPI app）掛載，跑在不同 port，
  絕不能掛進 `app/main.py` 的正式 app，以免污染正式流程。
"""
from __future__ import annotations

import json

from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

from app.config import settings
from app.schemas.chat import ChatRequest
from app.services import llm_service

router = APIRouter()


@router.get("/manifest")
def eval_manifest() -> dict:
    """回傳 eval server 目前實際載入的 model 與 prompt/tool 定義。

    Runner 端在寫 run manifest 時 fetch 此 endpoint，保證記錄下來的
    SYSTEM_PROMPT / SUBMIT_TOOL / CLAUDE_MODEL 就是本次 eval 真正跑的版本，
    而不是 runner 端 Python 環境看到的另一個版本。
    """
    return {
        "claude_model": settings.CLAUDE_MODEL,
        "system_prompt": llm_service.SYSTEM_PROMPT,
        "submit_tool": llm_service.SUBMIT_TOOL,
    }


@router.post("/chat")
async def eval_chat(request: ChatRequest):
    """Run one LLM turn and stream text / tool_use / done, nothing else.

    與正式 `/api/chat` 呼叫 `llm_service.stream_chat` 的參數完全一致
    （verified_phone / device_location / temperature），確保萃取行為相同。
    差別僅在：不對 tool_use 做任何後處理，直接把 LLM 原始輸出丟給 caller。
    """
    history_from_request = [
        {"role": m.role, "content": m.content} for m in request.history
    ]
    messages = history_from_request + [{"role": "user", "content": request.message}]

    stream_kwargs = {
        "verified_phone": request.verified_phone,
        "device_location": (
            request.device_location.model_dump()
            if request.device_location is not None
            else None
        ),
        "temperature": request.temperature,
    }

    async def event_generator():
        def _sse(data: dict) -> dict:
            return {"event": "message", "data": json.dumps(data, ensure_ascii=False)}

        async for chunk in llm_service.stream_chat(messages, **stream_kwargs):
            if chunk["type"] == "text":
                yield _sse(chunk)
            elif chunk["type"] == "tool_use":
                yield _sse({
                    "type": "tool_use",
                    "tool": chunk.get("tool"),
                    "tool_use_id": chunk.get("tool_use_id"),
                    "data": chunk.get("data"),
                })
            elif chunk["type"] == "done":
                yield _sse({"type": "done"})

    return EventSourceResponse(event_generator(), ping=15)
