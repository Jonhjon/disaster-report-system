import json
import logging
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import anthropic

logger = logging.getLogger(__name__)

from app.config import settings
from app.database import SessionLocal
from app.models.llm_log import LLMLog

MAX_HISTORY = 20  # 保留最近 20 則訊息，避免 token 過多

SYSTEM_PROMPT = """你是「智慧災害通報系統」的 AI 通報助手。你的任務是協助民眾通報災情。

## 你的角色
- 使用繁體中文
- 以冷靜、同理、專業的語氣與民眾對話
- 引導民眾提供完整的災情資訊

## 你需要收集的資訊
1. **災情種類**（必要）：人員受困、路段崩塌、淹水、土石流、建物受損、管線/電力受損、火警、其他
2. **災情地點**（必要）：盡量引導到具體地址、路名或知名地標
3. **嚴重程度**（必要）：1=輕微, 2=中等, 3=嚴重, 4=非常嚴重, 5=極嚴重
4. **發生時間**（必要）：什麼時候發生的，若民眾不確定請追問，確認無法提供後才可省略
5. **傷亡狀況**：死亡、受傷、受困人數
6. **詳細描述**：災情現場狀況

## 對話策略
- 先確認民眾安全
- 如果民眾一次提供很多資訊，直接整理並確認
- 如果資訊不足，逐步追問，但不要過於繁瑣
- 提交通報前，若尚未取得發生時間，必須先追問一次；若民眾明確表示不知道或無法回答，才可省略
- 詢問嚴重程度時，必須在問題中列出各級說明（1–5 級的描述），讓民眾能自行對應
- 至少收集到災情種類、地點、嚴重程度，且已詢問過發生時間後，才可提交通報
- 收集到足夠資訊後，呼叫 submit_disaster_report 工具提交通報
- 提交後告知民眾通報已成功

## 嚴重程度參考
- 1 輕微：小範圍影響，無人傷亡
- 2 中等：局部區域受影響，少數人需疏散
- 3 嚴重：較大範圍影響，有人受傷
- 4 非常嚴重：大範圍影響，多人傷亡
- 5 極嚴重：重大災害，大量傷亡或基礎設施嚴重損毀"""

SUBMIT_TOOL = {
    "name": "submit_disaster_report",
    "description": "當收集到足夠的災情資訊時，呼叫此工具提交正式災情通報",
    "input_schema": {
        "type": "object",
        "properties": {
            "disaster_type": {
                "type": "string",
                "enum": ["trapped", "road_collapse", "flooding", "landslide",
                         "building_damage", "utility_damage", "fire", "other"],
                "description": "災情類型"
            },
            "description":    {"type": "string", "description": "災情詳細描述"},
            "location_text":  {"type": "string", "description": "地點的文字描述"},
            "severity":       {"type": "integer", "minimum": 1, "maximum": 5},
            "latitude":       {"type": "number"},
            "longitude":      {"type": "number"},
            "casualties":     {"type": "integer", "minimum": 0},
            "injured":        {"type": "integer", "minimum": 0},
            "trapped":        {"type": "integer", "minimum": 0},
            "occurred_at":    {"type": "string", "description": "ISO 8601 格式"},
            "reporter_name":  {"type": "string"},
            "reporter_phone": {"type": "string"},
        },
        "required": ["disaster_type", "description", "location_text", "severity"]
    }
}


def _get_client() -> anthropic.AsyncAnthropic:
    return anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)


async def merge_event_descriptions(existing: str, new: str) -> str:
    """Use LLM to merge two disaster event descriptions into one."""
    if not existing:
        return new
    if not new or existing == new:
        return existing

    client = _get_client()
    try:
        message = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            messages=[{
                "role": "user",
                "content": (
                    "以下是同一災害事件的兩段描述，請整合成一段簡潔完整的繁體中文描述"
                    "（保留所有重要資訊，避免重複，不超過 200 字）：\n\n"
                    f"【原描述】{existing}\n\n【新描述】{new}\n\n只輸出整合後的描述，不要任何說明。"
                ),
            }],
        )
        merged = message.content[0].text.strip()
        return merged if merged else f"{existing}；{new}"
    except Exception:
        return f"{existing}；{new}"


async def reextract_numbers_from_description(description: str) -> dict:
    """從合併後的描述重新萃取 casualties/injured/trapped/severity。
    失敗或找不到時回傳 {}，呼叫端保留原 max() 值。"""
    if not description:
        return {}
    client = _get_client()
    try:
        message = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=100,
            messages=[{
                "role": "user",
                "content": (
                    "從以下災情描述中萃取數字資訊。"
                    "只輸出一個 JSON 物件，不要說明或程式碼區塊。\n"
                    "欄位：casualties(死亡), injured(受傷), trapped(受困) 為整數>=0，"
                    "severity 為 1-5 整數（1=輕微~5=極嚴重）。"
                    "找不到則填 null。\n"
                    '格式：{"casualties":...,"injured":...,"trapped":...,"severity":...}\n\n'
                    f"描述：{description}"
                ),
            }],
        )
        raw = message.content[0].text.strip()
        # 防禦：移除可能的 markdown code fence
        if raw.startswith("```"):
            parts = raw.split("```")
            raw = parts[1].lstrip("json").strip() if len(parts) > 1 else raw
        data = json.loads(raw)
        result = {}
        for key in ("casualties", "injured", "trapped"):
            val = data.get(key)
            if val is not None:
                result[key] = int(val)
        val = data.get("severity")
        if val is not None:
            sev = int(val)
            if 1 <= sev <= 5:
                result["severity"] = sev
        return result
    except Exception:
        return {}


async def stream_chat(messages: list[dict]):
    """Stream chat response from Claude with tool use support.

    Yields dicts: {"type": "text", "content": str}
                  {"type": "tool_use", "tool": str, "data": dict}
                  {"type": "done"}
    """
    client = _get_client()

    if len(messages) > MAX_HISTORY:
        messages = messages[-MAX_HISTORY:]

    claude_msgs = [{"role": m["role"], "content": m["content"]} for m in messages]

    tw_now = datetime.now(ZoneInfo("Asia/Taipei")).strftime("%Y年%m月%d日 %H:%M")
    system = SYSTEM_PROMPT + f"\n\n## 當前時間\n現在是 {tw_now}（台灣時間）。推斷發生時間時請以此為基準。"

    start_time = time.time()
    tool_name = None
    tool_input_parts: list[str] = []
    output_parts: list[str] = []
    status = "success"
    token_usage: dict = {}
    prompt = messages[-1]["content"] if messages else ""

    try:
        async with client.messages.stream(
            model=settings.CLAUDE_MODEL,
            max_tokens=1024,
            system=system,
            messages=claude_msgs,
            tools=[SUBMIT_TOOL],
        ) as stream:
            async for event in stream:
                if event.type == "content_block_start":
                    if event.content_block.type == "tool_use":
                        tool_name = event.content_block.name
                        tool_input_parts = []

                elif event.type == "content_block_delta":
                    if event.delta.type == "text_delta":
                        output_parts.append(event.delta.text)
                        yield {"type": "text", "content": event.delta.text}
                    elif event.delta.type == "input_json_delta":
                        tool_input_parts.append(event.delta.partial_json)

                elif event.type == "content_block_stop":
                    if tool_name:
                        tool_data = json.loads("".join(tool_input_parts))
                        yield {"type": "tool_use", "tool": tool_name, "data": tool_data}
                        tool_name = None
                        tool_input_parts = []

            final_msg = await stream.get_final_message()
            usage = final_msg.usage
            token_usage = {
                "input_tokens": usage.input_tokens,
                "output_tokens": usage.output_tokens,
                "total_tokens": usage.input_tokens + usage.output_tokens,
            }

        yield {"type": "done"}

    except anthropic.RateLimitError:
        status = "429"
        yield {"type": "text", "content": "⚠️ API 請求過於頻繁，請稍後再試。"}
        yield {"type": "done"}
    except anthropic.AuthenticationError:
        status = "error"
        yield {"type": "text", "content": "⚠️ API 金鑰無效，請聯絡系統管理員。"}
        yield {"type": "done"}
    except Exception as e:
        status = "error"
        logger.exception("stream_chat unexpected error: %s", e)
        yield {"type": "text", "content": "⚠️ 系統發生錯誤，請稍後再試。"}
        yield {"type": "done"}
    finally:
        db = SessionLocal()
        try:
            db.add(LLMLog(
                timestamp=datetime.now(timezone.utc),
                model=settings.CLAUDE_MODEL,
                latency_ms=int((time.time() - start_time) * 1000),
                input_tokens=token_usage.get("input_tokens", 0),
                output_tokens=token_usage.get("output_tokens", 0),
                total_tokens=token_usage.get("total_tokens", 0),
                status=status,
                prompt=prompt,
                output="".join(output_parts),
            ))
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()
