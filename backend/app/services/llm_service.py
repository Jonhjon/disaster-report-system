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

MODEL = settings.CLAUDE_MODEL

SYSTEM_PROMPT = """你是「智慧災害通報系統」的 AI 通報助手。你的任務是協助民眾通報災情。

## 你的角色
- 使用繁體中文
- 以冷靜、同理、專業的語氣與民眾對話
- 引導民眾提供完整的災情資訊

## 你需要收集的資訊
1. **災情種類**（必要）：人員受困、路段崩塌、淹水、小型土石流、建物受損、管線/電力受損、火警、其他
2. **災情地點**（必要）：盡量引導到具體地址、路名或知名地標
3. **嚴重程度**（必要）：1=輕微, 2=中等, 3=嚴重, 4=非常嚴重, 5=極嚴重
4. **發生時間**（必要）：什麼時候發生的，若民眾不確定請追問，確認無法提供後才可省略
5. **傷亡狀況**（必要）：死亡（casualties）、受傷（injured）、受困（trapped）人數
   - 受傷（injured）：有身體傷害的人員，含正在等待救護車的燒傷／受傷者
   - 受困（trapped）：無法自行脫離現場、需要搜救的人員（如被瓦礫壓住、受困電梯）
   - 「等待救援／救護」不等於受困，應計入 injured
6. **詳細描述**：災情現場狀況

## 對話策略
- 先確認民眾安全
- 如果民眾一次提供很多資訊，直接整理並確認
- 如果資訊不足，逐步追問，但不要過於繁瑣
- 提交通報前，若尚未取得發生時間，必須先追問一次；若民眾明確表示不知道或無法回答，才可省略
- 詢問嚴重程度時，必須在問題中列出各級說明（1–5 級的描述），讓民眾能自行對應
- 至少收集到災情種類、地點、嚴重程度，且已詢問過發生時間後，才可提交通報
- 收集到足夠資訊後，呼叫 submit_disaster_report 工具提交通報
- 如果系統回傳相似事件清單要求使用者選擇，請以自然語言列出各候選事件（含標題、通報數、距離），並詢問使用者要合併到哪個事件或建立新事件。使用者選擇後，再次呼叫 submit_disaster_report 並填入 merge_event_id（事件 UUID 或 'new'）
- 提交後告知民眾通報已成功
- 只根據使用者明確說明的內容填寫傷亡數字；若使用者未回答某個問題，該欄位填 0，不可從模糊措辭或未回答的問題中自行推斷

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
                         "small_landslide", "building_damage", "utility_damage", "fire", "other"],
                "description": "災情類型"
            },
            "description":    {"type": "string", "description": "災情詳細描述"},
            "location_text":  {"type": "string", "description": "地點的文字描述（必須為具體地址、路名或知名地標，不可只填縣市名稱）"},
            "severity":       {"type": "integer", "minimum": 1, "maximum": 5},
            "casualties":     {"type": "integer", "minimum": 0},
            "injured":        {"type": "integer", "minimum": 0},
            "trapped":        {"type": "integer", "minimum": 0, "description": "受困人數：無法自行脫離現場、需要搜救的人員（如被瓦礫壓住、受困電梯）。等待救護車的傷者應計入 injured，不應計入 trapped"},
            "occurred_at":    {"type": "string", "description": "ISO 8601 格式"},
            "merge_event_id": {
                "type": "string",
                "description": "使用者選擇要合併的事件 UUID。若使用者選擇建立新事件，填入 'new'。僅在系統提示需要使用者選擇時才使用此欄位。"
            },
            "reporter_name":  {"type": "string"},
            "reporter_phone": {"type": "string"},
        },
        "required": ["disaster_type", "description", "location_text", "severity"]
    }
}


def _strip_thinking(text: str, state: dict) -> str:
    """過濾文字片段中嵌入的 <thinking>...</thinking> 標籤。

    state 必須包含 {"in_thinking": bool}，跨 chunk 持有狀態。
    回傳過濾後的可見文字。
    """
    result = []
    remaining = text
    while remaining:
        if state["in_thinking"]:
            end = remaining.find("</thinking>")
            if end == -1:
                # 整段都在 thinking 中，丟棄
                break
            else:
                # 離開 thinking，繼續處理後面的文字
                state["in_thinking"] = False
                remaining = remaining[end + len("</thinking>"):]
        else:
            start = remaining.find("<thinking>")
            if start == -1:
                # 沒有 thinking 標籤，全部輸出
                result.append(remaining)
                break
            else:
                # 標籤前的文字輸出，進入 thinking
                result.append(remaining[:start])
                state["in_thinking"] = True
                remaining = remaining[start + len("<thinking>"):]
    return "".join(result)


def _get_client() -> anthropic.AsyncAnthropic:
    return anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    # return anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY, base_url="https://api.banana2556.com" )


async def merge_event_descriptions(existing: str, new: str) -> str:
    """Use LLM to merge two disaster event descriptions into one."""
    if not existing:
        return new
    if not new or existing == new:
        return existing

    client = _get_client()
    try:
        message = await client.messages.create(
            # model="claude-haiku-4-5-20251001",
            model=MODEL,
            max_tokens=300,
            messages=[{
                "role": "user",
                "content": (
                    "以下是同一災害事件在不同時間點收到的兩筆通報描述，來自不同通報者。\n"
                    "請整合成一段簡潔完整的繁體中文描述（不超過 200 字），依照以下規則處理傷亡人數：\n"
                    "1. 若新通報使用「又有」「另外」「還有」「新增」等明確新增詞彙，"
                    "代表是新增的不同人員，請將兩段描述的傷亡人數累計，"
                    "並用「共 N 人受傷，其中 X 人輕傷、Y 人重傷」的格式呈現。\n"
                    "2. 若新通報未使用新增詞彙，視為對同批傷者的狀態更新，"
                    "以新通報的傷情描述取代舊描述，傷者人數以新通報為準。\n"
                    "3. 保留地點、火勢、時間等非人員資訊，合理整合不重複。\n\n"
                    f"【原通報描述】{existing}\n\n【新通報描述】{new}\n\n"
                    "只輸出整合後的描述，不要任何說明。"
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
            # model="claude-haiku-4-5-20251001",
            model=MODEL,
            max_tokens=100,
            messages=[{
                "role": "user",
                "content": (
                    "從以下災情描述中萃取數字資訊。"
                    "只輸出一個 JSON 物件，不要說明或程式碼區塊。\n"
                    "欄位：casualties(死亡), injured(受傷), trapped(受困) 為整數>=0，"
                    "severity 為 1-5 整數（1=輕微~5=極嚴重）。"
                    "找不到則填 null。\n"
                    "若描述中分組列出傷者（如「3 人輕傷、3 人重傷」），請將各組加總後填入 injured。\n"
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
    tool_use_id: str | None = None
    tool_input_parts: list[str] = []
    output_parts: list[str] = []
    status = "success"
    token_usage: dict = {}
    prompt = messages[-1]["content"] if messages else ""
    in_thinking_block = False
    thinking_state: dict = {"in_thinking": False}

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
                        tool_use_id = event.content_block.id
                        tool_input_parts = []
                    elif event.content_block.type == "thinking":
                        in_thinking_block = True

                elif event.type == "content_block_delta":
                    if event.delta.type == "text_delta" and not in_thinking_block:
                        visible = _strip_thinking(event.delta.text, thinking_state)
                        if visible:
                            output_parts.append(visible)
                            yield {"type": "text", "content": visible}
                    elif event.delta.type == "input_json_delta":
                        tool_input_parts.append(event.delta.partial_json)
                    # thinking_delta 直接忽略

                elif event.type == "content_block_stop":
                    if in_thinking_block:
                        in_thinking_block = False
                    elif tool_name:
                        tool_data = json.loads("".join(tool_input_parts))
                        yield {"type": "tool_use", "tool": tool_name, "data": tool_data, "tool_use_id": tool_use_id}
                        tool_name = None
                        tool_use_id = None
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
