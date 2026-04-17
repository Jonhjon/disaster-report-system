# 智慧災害通報系統 - 資料庫設計

## 概要
使用 PostgreSQL 16 + PostGIS 3，透過 SQLAlchemy 2.0 + GeoAlchemy2 操作。
資料庫遷移使用 Alembic，目前版本：007（含 users 表）。

---

## 表 1: disaster_events (災情事件)

一個「事件」代表一個獨立的災害（例如：某處火災），可由多筆通報歸納而成。

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
| status | VARCHAR(20) | DEFAULT 'reported' | 狀態: reported/in_progress/resolved |
| report_count | INTEGER | DEFAULT 1 | 關聯通報數量 |
| location_approximate | BOOLEAN | DEFAULT false | 位置是否不精確 |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | 建立時間 |
| updated_at | TIMESTAMPTZ | DEFAULT NOW() | 最後更新時間 |

### 索引
- `idx_events_location` — GIST 空間索引 on `location`
- `idx_events_disaster_type` — B-tree on `disaster_type`
- `idx_events_status` — B-tree on `status`
- `idx_events_occurred_at` — B-tree on `occurred_at`
- `idx_events_severity` — B-tree on `severity`

### CHECK 約束
- `ck_severity_range`: `severity >= 1 AND severity <= 5`
- `ck_status_values`: `status IN ('reported', 'in_progress', 'resolved')`

### disaster_type 可選值
| 值 | 中文 |
|----|------|
| trapped | 人員受困 |
| road_collapse | 路段崩塌 |
| flooding | 淹水 |
| landslide | 土石流 |
| small_landslide | 小型土石流 |
| building_damage | 建物受損 |
| utility_damage | 管線/電力受損 |
| fire | 火警 |
| other | 其他 |

### status 可選值
| 值 | 中文 | 說明 |
|----|------|------|
| reported | 通報中 | 災情已通報，尚未處理 |
| in_progress | 處理中 | 災情正在處理中 |
| resolved | 已結案 | 災情已處理完畢 |

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
| geocoded_address | VARCHAR(500) | | Geocoding 結果地址 |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | 通報時間 |

### 索引
- `idx_reports_event_id` — B-tree on `event_id`
- `idx_reports_location` — GIST 空間索引 on `location`
- `idx_reports_created_at` — B-tree on `created_at`

---

## 表 3: users (管理員帳號)

管理中心端登入用的帳號資料。

| 欄位 | 型別 | 約束 | 說明 |
|------|------|------|------|
| id | UUID | PK, DEFAULT gen_random_uuid() | 主鍵 |
| username | VARCHAR(50) | UNIQUE, NOT NULL | 帳號 |
| hashed_password | VARCHAR(255) | NOT NULL | bcrypt 雜湊密碼 |
| display_name | VARCHAR(100) | | 顯示名稱 |
| is_active | BOOLEAN | DEFAULT true | 是否啟用 |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | 建立時間 |

預設管理員帳號：`admin` / `admin123`（部署時應更改密碼）

---

## 表 4: llm_logs (LLM 呼叫日誌)

記錄所有 Claude API 呼叫，用於監控和成本追蹤。

| 欄位 | 型別 | 約束 | 說明 |
|------|------|------|------|
| id | UUID | PK, DEFAULT gen_random_uuid() | 主鍵 |
| timestamp | TIMESTAMPTZ | | 呼叫時間 |
| model | VARCHAR(100) | | 使用的模型名稱 |
| latency_ms | INTEGER | | 回應延遲（毫秒） |
| input_tokens | INTEGER | | 輸入 token 數 |
| output_tokens | INTEGER | | 輸出 token 數 |
| total_tokens | INTEGER | | 總 token 數 |
| status | VARCHAR(20) | | 狀態 (success/error) |
| prompt | TEXT | | 請求的 prompt |
| output | TEXT | | AI 的回應 |

---

## 關聯關係

```
disaster_events (1) ←──── (N) disaster_reports
   一個事件可以有多筆通報

users — 獨立表，無外鍵關聯
llm_logs — 獨立表，無外鍵關聯
```

---

## Alembic 遷移歷史

| 版本 | 說明 |
|------|------|
| 001 | 初始：建立 disaster_events、disaster_reports 表 |
| 002 | 建立 llm_logs 表 |
| 003 | 新增 disaster_reports.geocoded_address 欄位 |
| 004 | 新增 disaster_events.location_approximate 欄位 |
| 005 | 重新命名狀態值：active → open, monitoring → in_progress |
| 006 | 重新命名狀態值：open → reported |
| 007 | 建立 users 表，插入預設管理員帳號 |
