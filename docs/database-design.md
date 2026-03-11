# 智慧災害通報系統 - 資料庫設計

## 概要
使用 PostgreSQL 16 + PostGIS 3，透過 SQLAlchemy 2.0 + GeoAlchemy2 操作。

---

## 表 1: disaster_events (災情事件)

一個「事件」代表一個獨立的災害（例如：某地震引發的某處坍方），可由多筆通報歸納而成。

| 欄位 | 型別 | 約束 | 說明 |
|------|------|------|------|
| id | UUID | PK, DEFAULT gen_random_uuid() | 主鍵 |
| title | VARCHAR(200) | NOT NULL | 事件標題（LLM 自動產生） |
| disaster_type | VARCHAR(50) | NOT NULL | 災情種類 |
| severity | INTEGER | NOT NULL, CHECK(1-5) | 嚴重程度 1=輕微~5=極嚴重 |
| description | TEXT | | 災情描述（LLM 整合摘要） |
| location_text | VARCHAR(500) | NOT NULL | 地點文字描述 |
| location | GEOMETRY(Point, 4326) | NOT NULL | PostGIS 經緯度座標 |
| occurred_at | TIMESTAMPTZ | NOT NULL | 災情發生時間 |
| casualties | INTEGER | DEFAULT 0 | 死亡人數 |
| injured | INTEGER | DEFAULT 0 | 受傷人數 |
| trapped | INTEGER | DEFAULT 0 | 受困人數 |
| status | VARCHAR(20) | DEFAULT 'active' | 狀態: active/monitoring/resolved |
| report_count | INTEGER | DEFAULT 1 | 關聯通報數量 |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | 建立時間 |
| updated_at | TIMESTAMPTZ | DEFAULT NOW() | 最後更新時間 |

### 索引
- `idx_events_location` — GIST 空間索引 on `location`
- `idx_events_disaster_type` — B-tree on `disaster_type`
- `idx_events_status` — B-tree on `status`
- `idx_events_occurred_at` — B-tree on `occurred_at`
- `idx_events_severity` — B-tree on `severity`

### disaster_type 可選值
| 值 | 中文 |
|----|------|
| earthquake | 地震 |
| typhoon | 颱風 |
| flood | 水災 |
| landslide | 土石流/坍方 |
| fire | 火災 |
| other | 其他 |

### status 可選值
| 值 | 中文 | 說明 |
|----|------|------|
| active | 進行中 | 災情正在發生或尚未處理 |
| monitoring | 監控中 | 災情已受控，持續觀察 |
| resolved | 已解除 | 災情已處理完畢 |

---

## 表 2: disaster_reports (災情通報)

每筆民眾通報記錄，關聯到一個事件。

| 欄位 | 型別 | 約束 | 說明 |
|------|------|------|------|
| id | UUID | PK, DEFAULT gen_random_uuid() | 主鍵 |
| event_id | UUID | FK → disaster_events(id), NULLABLE | 關聯的災情事件 |
| reporter_name | VARCHAR(100) | | 通報者姓名（可選） |
| reporter_phone | VARCHAR(20) | | 通報者電話（可選） |
| raw_message | TEXT | NOT NULL | 通報原始對話內容 |
| extracted_data | JSONB | NOT NULL | LLM 擷取的結構化資料 |
| location | GEOMETRY(Point, 4326) | | 通報地點座標 |
| location_text | VARCHAR(500) | | 通報地點文字 |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | 通報時間 |

### 索引
- `idx_reports_event_id` — B-tree on `event_id`
- `idx_reports_location` — GIST 空間索引 on `location`
- `idx_reports_created_at` — B-tree on `created_at`

### extracted_data JSONB 結構範例
```json
{
  "disaster_type": "flood",
  "description": "台北市中正區忠孝東路一段淹水約50公分",
  "location_text": "台北市中正區忠孝東路一段",
  "latitude": 25.0418,
  "longitude": 121.5199,
  "severity": 3,
  "casualties": 0,
  "injured": 2,
  "trapped": 0,
  "occurred_at": "2026-02-25T10:30:00+08:00",
  "reporter_name": "王小明",
  "reporter_phone": "0912345678"
}
```

---

## 關聯關係

```
disaster_events (1) ←──── (N) disaster_reports
   一個事件可以有多筆通報
```

---

## 去重查詢範例 (PostGIS)

查詢某座標半徑 20km 內、72 小時內、同類型的 active 事件：

```sql
SELECT *
FROM disaster_events
WHERE status = 'active'
  AND disaster_type = :disaster_type
  AND occurred_at >= NOW() - INTERVAL '72 hours'
  AND ST_DWithin(
    location::geography,
    ST_SetSRID(ST_MakePoint(:longitude, :latitude), 4326)::geography,
    :radius_meters  -- 例如 20000 (20km)
  )
ORDER BY ST_Distance(
  location::geography,
  ST_SetSRID(ST_MakePoint(:longitude, :latitude), 4326)::geography
)
LIMIT 5;
```
