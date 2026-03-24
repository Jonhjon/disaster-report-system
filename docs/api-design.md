# 智慧災害通報系統 - API 設計

## 基本設定
- Base URL: `http://localhost:8000/api`
- 格式: JSON
- 時間格式: ISO 8601 with timezone

---

## Chat API

### POST /api/chat
傳送對話訊息，回傳 AI 回覆（streaming SSE）。

**Request Body:**
```json
{
  "message": "我要通報災情",
  "conversation_id": "uuid-or-null",
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
data: {"type": "tool_use", "tool": "submit_disaster_report", "data": {...}}
data: {"type": "done"}
```

當 Claude 呼叫 `submit_disaster_report` tool 時，後端：
1. 接收結構化資料
2. 執行 Geocoding（若無座標）
3. 執行事件去重
4. 建立/更新事件
5. 回傳結果給前端顯示

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
| status | string | 篩選狀態 |
| date_from | datetime | 起始時間 |
| date_to | datetime | 結束時間 |
| sort_by | string | 排序欄位: occurred_at/severity/report_count/created_at |
| sort_order | string | asc/desc |
| page | int | 頁碼（從 1 開始） |
| page_size | int | 每頁筆數（預設 20） |

**Response:**
```json
{
  "items": [
    {
      "id": "uuid",
      "title": "台北市中正區忠孝東路淹水",
      "disaster_type": "flood",
      "severity": 3,
      "description": "...",
      "location_text": "台北市中正區忠孝東路一段",
      "latitude": 25.0418,
      "longitude": 121.5199,
      "occurred_at": "2026-02-25T10:30:00+08:00",
      "casualties": 0,
      "injured": 2,
      "trapped": 0,
      "status": "active",
      "report_count": 3,
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

### GET /api/events/{id}
取得單一事件詳情。

**Response:** 單一事件物件（同上格式）

### PUT /api/events/{id}
更新事件資訊。

**Request Body:**
```json
{
  "title": "更新後的標題",
  "severity": 4,
  "status": "monitoring",
  "description": "更新後的描述",
  "casualties": 1,
  "injured": 5,
  "trapped": 0
}
```

### PATCH /api/events/{id}/location
更新事件位置資訊（地址修正用）。

**Request Body:**
```json
{
  "location_text": "台北市中正區重慶南路一段122號",
  "latitude": 25.0418,
  "longitude": 121.5199,
  "location_approximate": false
}
```

**Response:** 更新後的事件物件（同 GET /api/events/{id} 格式）

### GET /api/events/{id}/reports
取得事件的所有通報。

**Response:**
```json
{
  "items": [
    {
      "id": "uuid",
      "event_id": "uuid",
      "reporter_name": "王小明",
      "raw_message": "對話內容...",
      "extracted_data": {},
      "location_text": "...",
      "created_at": "..."
    }
  ],
  "total": 3
}
```

### GET /api/events/map
取得地圖範圍內的事件。

**Query Parameters:**
| 參數 | 型別 | 說明 |
|------|------|------|
| bounds | string | 地圖範圍 "south,west,north,east" |
| disaster_type | string | 篩選災情種類（可選） |
| severity_min | int | 最低嚴重程度（可選） |
| status | string | 篩選狀態（可選，預設 active） |

**Response:**
```json
{
  "items": [
    {
      "id": "uuid",
      "title": "...",
      "disaster_type": "flood",
      "severity": 3,
      "latitude": 25.0418,
      "longitude": 121.5199,
      "status": "active",
      "report_count": 3,
      "occurred_at": "..."
    }
  ]
}
```

---

## Reports API

### GET /api/reports
取得通報列表。

**Query Parameters:**
| 參數 | 型別 | 說明 |
|------|------|------|
| page | int | 頁碼 |
| page_size | int | 每頁筆數 |

### GET /api/reports/{id}
取得單一通報詳情。

---

## Claude Tool Use 定義

### submit_disaster_report
```json
{
  "name": "submit_disaster_report",
  "description": "當已收集到足夠的災情資訊時，呼叫此工具提交災情通報。至少需要收集到災情種類、地點描述、嚴重程度。",
  "input_schema": {
    "type": "object",
    "properties": {
      "disaster_type": {
        "type": "string",
        "enum": ["earthquake", "typhoon", "flood", "landslide", "fire", "other"],
        "description": "災情種類"
      },
      "description": {
        "type": "string",
        "description": "災情詳細描述"
      },
      "location_text": {
        "type": "string",
        "description": "災情地點的文字描述（地址、路名、地標等）"
      },
      "latitude": {
        "type": "number",
        "description": "緯度（若能推斷）"
      },
      "longitude": {
        "type": "number",
        "description": "經度（若能推斷）"
      },
      "severity": {
        "type": "integer",
        "minimum": 1,
        "maximum": 5,
        "description": "嚴重程度：1=輕微, 2=中等, 3=嚴重, 4=非常嚴重, 5=極嚴重"
      },
      "casualties": {
        "type": "integer",
        "description": "死亡人數"
      },
      "injured": {
        "type": "integer",
        "description": "受傷人數"
      },
      "trapped": {
        "type": "integer",
        "description": "受困人數"
      },
      "occurred_at": {
        "type": "string",
        "format": "date-time",
        "description": "災情發生時間 (ISO 8601)"
      },
      "reporter_name": {
        "type": "string",
        "description": "通報者姓名"
      },
      "reporter_phone": {
        "type": "string",
        "description": "通報者聯絡電話"
      }
    },
    "required": ["disaster_type", "description", "location_text", "severity"]
  }
}
```

### Claude System Prompt 設計要點
- 使用繁體中文
- 以冷靜、同理、專業的語氣引導民眾通報
- 至少確認：災情種類、地點、嚴重程度
- 主動追問遺漏的重要資訊（傷亡、受困等）
- 地點盡量引導到具體地址或地標
- 收集充分資訊後呼叫 submit_disaster_report tool
- 提交後向民眾確認通報已收到
