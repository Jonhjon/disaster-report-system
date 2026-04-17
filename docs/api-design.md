# 智慧災害通報系統 - API 設計

## 基本設定
- Base URL: `http://localhost:8000/api`
- 格式: JSON
- 時間格式: ISO 8601 with timezone
- 認證: JWT Bearer Token（僅管理端點需要）

---

## 認證機制

管理端點需要在 HTTP Header 中帶入 JWT Token：
```
Authorization: Bearer <token>
```

Token 透過登入 API 取得，有效期 8 小時。

### 公開端點（免認證）
- `POST /api/chat`
- `GET /api/events`
- `GET /api/events/map`
- `GET /api/events/{id}`
- `GET /api/events/{id}/reports`
- `GET /api/reports`
- `GET /api/reports/{id}`

### 受保護端點（需 JWT）
- `PUT /api/events/{id}`
- `DELETE /api/events/{id}`
- `PATCH /api/events/{id}/location`
- `GET /api/llm-logs`

---

## Auth API

### POST /api/auth/login
管理員登入，取得 JWT Token。

**Request:** `application/x-www-form-urlencoded`
| 參數 | 型別 | 說明 |
|------|------|------|
| username | string | 帳號 |
| password | string | 密碼 |

**Response 200:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer"
}
```

**Response 401:**
```json
{
  "detail": "帳號或密碼錯誤"
}
```

### GET /api/auth/me
取得當前登入用戶資訊。**需認證。**

**Response 200:**
```json
{
  "id": "uuid",
  "username": "admin",
  "display_name": "系統管理員",
  "is_active": true
}
```

---

## Chat API

### POST /api/chat
傳送對話訊息，回傳 AI 回覆（streaming SSE）。

**Request Body:**
```json
{
  "message": "台北市信義區發生淹水",
  "history": [
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."}
  ]
}
```

**Response:** Server-Sent Events (SSE) streaming
```
data: {"type": "text", "content": "請問"}
data: {"type": "text", "content": "您在哪裡"}
data: {"type": "candidates_selection", "candidates": [...]}
data: {"type": "report_submitted", "status": "created", "event_id": "uuid", "message": "..."}
data: {"type": "done"}
data: {"type": "error", "message": "錯誤訊息"}
```

SSE 事件類型說明：
| type | 說明 |
|------|------|
| text | AI 回覆文字片段 |
| candidates_selection | 偵測到相似事件，附帶候選清單供使用者選擇 |
| report_submitted | 通報完成（status: "created" 或 "merged"） |
| done | 串流結束 |
| error | 發生錯誤 |

### candidates_selection 事件格式
```json
{
  "type": "candidates_selection",
  "candidates": [
    {
      "event_id": "uuid",
      "title": "花蓮縣餅前站火警",
      "description": "...",
      "location_text": "花蓮火車站前站",
      "report_count": 2,
      "distance_m": 30,
      "score": 0.85
    }
  ]
}
```

---

## Events API

### GET /api/events
取得災情事件列表（支援篩選、排序、分頁）。

**Query Parameters:**
| 參數 | 型別 | 說明 |
|------|------|------|
| search | string | 關鍵字搜尋（標題、描述、地點） |
| disaster_type | string | 篩選災情種類 |
| severity_min | int | 最低嚴重程度 |
| severity_max | int | 最高嚴重程度 |
| status | string | 篩選狀態 (reported/in_progress/resolved) |
| date_from | datetime | 起始時間 |
| date_to | datetime | 結束時間 |
| sort_by | string | 排序欄位: occurred_at/severity/report_count/created_at |
| sort_order | string | asc/desc |
| page | int | 頁碼（從 1 開始，預設 1） |
| page_size | int | 每頁筆數（預設 20，最多 100） |

**Response 200:**
```json
{
  "items": [
    {
      "id": "uuid",
      "title": "台北市信義區淹水",
      "disaster_type": "flooding",
      "severity": 3,
      "description": "...",
      "location_text": "台北市信義區仁愛路四段",
      "latitude": 25.0418,
      "longitude": 121.5199,
      "occurred_at": "2026-04-10T10:30:00+08:00",
      "casualties": 0,
      "injured": 2,
      "trapped": 0,
      "status": "reported",
      "report_count": 3,
      "location_approximate": false,
      "created_at": "...",
      "updated_at": "..."
    }
  ],
  "total": 42,
  "page": 1,
  "page_size": 20,
  "total_pages": 3
}
```

### GET /api/events/map
取得地圖範圍內的事件（輕量版回應）。

**Query Parameters:**
| 參數 | 型別 | 說明 |
|------|------|------|
| bounds | string | 地圖範圍 "south,west,north,east" |
| disaster_type | string | 篩選災情種類 |
| severity_min | int | 最低嚴重程度 |
| status | string | 篩選狀態（預設 reported） |

**Response 200:**
```json
{
  "items": [
    {
      "id": "uuid",
      "title": "...",
      "disaster_type": "flooding",
      "severity": 3,
      "latitude": 25.0418,
      "longitude": 121.5199,
      "status": "reported",
      "report_count": 3,
      "occurred_at": "...",
      "location_approximate": false
    }
  ]
}
```

### GET /api/events/{id}
取得單一事件詳情。

### PUT /api/events/{id} 🔒
更新事件資訊。**需認證。**

**Request Body:**
```json
{
  "title": "更新後的標題",
  "severity": 4,
  "status": "in_progress",
  "description": "更新後的描述",
  "casualties": 1,
  "injured": 5,
  "trapped": 0
}
```

### PATCH /api/events/{id}/location 🔒
修正事件位置（重新 Geocoding）。**需認證。**

**Request Body:**
```json
{
  "location_text": "台北市中正區重慶南路一段122號"
}
```

### DELETE /api/events/{id} 🔒
刪除事件。**需認證。** 回傳 204 No Content。

### GET /api/events/{id}/reports
取得事件的所有通報。

**Response 200:**
```json
{
  "items": [
    {
      "id": "uuid",
      "event_id": "uuid",
      "reporter_name": "王小明",
      "reporter_phone": null,
      "raw_message": "對話內容...",
      "extracted_data": {},
      "location_text": "...",
      "geocoded_address": "...",
      "created_at": "..."
    }
  ],
  "total": 3
}
```

---

## Reports API

### GET /api/reports
取得通報列表（分頁）。

**Query Parameters:**
| 參數 | 型別 | 說明 |
|------|------|------|
| page | int | 頁碼（預設 1） |
| page_size | int | 每頁筆數（預設 20，最多 100） |

### GET /api/reports/{id}
取得單一通報詳情。

---

## Monitor API

### GET /api/llm-logs 🔒
取得最近 100 筆 LLM 呼叫日誌。**需認證。**

**Response 200:**
```json
[
  {
    "id": "uuid",
    "timestamp": "2026-04-10T12:00:00+00:00",
    "model": "claude-haiku-4-5-20251001",
    "latency_ms": 1234,
    "token_usage": {
      "input_tokens": 500,
      "output_tokens": 200,
      "total_tokens": 700
    },
    "status": "success",
    "prompt": "...",
    "output": "..."
  }
]
```

---

## 錯誤回應格式

**401 Unauthorized:**
```json
{
  "detail": "無效的認證憑證"
}
```

**404 Not Found:**
```json
{
  "detail": "Event not found"
}
```

**422 Validation Error:**
```json
{
  "detail": "無法 geocode 此地址，請提供更具體的地址"
}
```
