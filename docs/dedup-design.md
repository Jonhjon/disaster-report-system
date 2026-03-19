# 去重複（Dedup）機制設計文件

**對應原始碼：** `backend/app/services/dedup_service.py`

---

## 目的

當多名民眾同時通報同一災害事件時，系統需避免產生重複紀錄。去重機制在新通報寫入資料庫前，判斷它是否與既有事件描述相同。

---

## 整體流程

```
新通報進來
    │
    ▼
[第一關] find_candidate_events()
  條件：類型相同 + 時間窗口內 + 地理範圍內
  結果：最多 5 筆候選事件
    │
    ▼（對每筆候選逐一比對）
[第二關] is_duplicate()
    │
    ├─ _compute_dedup_score() → 四維度加權分數
    │
    ├─ score > 0.80  ──────────► 判定重複
    ├─ score 0.50~0.80 ────────► 交由 LLM 判斷
    └─ score < 0.50  ──────────► 判定為新事件
```

---

## 第一關：候選粗篩

`find_candidate_events()` 使用 PostGIS `ST_DWithin` 進行空間查詢，同時套用三個硬性過濾條件：

| 條件 | 說明 |
|------|------|
| `status == "active"` | 僅比對仍活躍的事件 |
| `disaster_type` 相同 | 類型不同直接排除 |
| `occurred_at >= cutoff` | 在時間窗口內（見下表） |
| 地理距離 ≤ 半徑 | 依類型而定（見下表） |

結果依距離升冪排序，取最近 **5 筆**。

### 去重半徑（DEDUP_RADIUS）

| 災害類型 | 半徑 |
|---------|------|
| trapped | 1 km |
| building_damage | 1 km |
| road_collapse | 2 km |
| utility_damage | 2 km |
| landslide | 3 km |
| other | 3 km |
| flooding | 5 km |
| fire | 5 km |
| 未定義類型 | 10 km（預設值） |

### 去重時間窗口（DEDUP_HOURS_BY_TYPE）

| 災害類型 | 窗口 |
|---------|------|
| fire | 12 小時 |
| 其他所有類型 | 72 小時（預設值） |

---

## 第二關：四維度加權評分

`_compute_dedup_score()` 從四個維度計算 0–1 的相似分數：

```
總分 = 0.3 × 語意 + 0.3 × 地理 + 0.2 × 時間 + 0.2 × 類型
```

### 1. 語意相似度（30%）

使用 **jieba** 對新通報描述與候選的 `title + description` 分別斷詞，計算 Jaccard 係數：

```
semantic_score = |交集詞| / |聯集詞|
```

### 2. 地理距離（30%）

使用 Haversine 公式計算實際距離（km），與去重半徑正規化：

```
geo_score = max(0, 1 - 實際距離km / 最大半徑km)
```

若無法取得候選座標（如測試環境），fallback 為 `0.5`。

### 3. 時間接近度（20%）

| 時間差 | time_score |
|--------|-----------|
| ≤ 1 小時 | 1.0 |
| 1–24 小時 | 線性從 1.0 降至 0.2 |
| ≥ 24 小時 | 0.2 |

公式（1–24 小時區間）：
```
time_score = 1.0 - 0.8 × (hours_diff - 1) / 23
```

> **注意**：資料庫若儲存 naive datetime，此處一律視為 UTC 處理。若實際時區為 UTC+8，時間差計算將有 8 小時偏差。

### 4. 類型符合（20%）

```
type_score = 1.0（相同類型）或 0.0（不同類型）
```

> 因粗篩已強制過濾相同類型，進入精判的候選此分數恆為 `1.0`，等同固定加分 0.2。

---

## 第三關：LLM 輔助判斷

當分數落在灰色地帶（`0.50 ≤ score ≤ 0.80`）時，呼叫 `llm_judge_duplicate()`：

- **模型**：Claude Haiku（`claude-haiku-4-5-20251001`）
- **Prompt**：「以下兩則通報是否描述同一個災害事件？請只回答 YES 或 NO。」
- **Fallback**：LLM 不可用時改用 `difflib.SequenceMatcher`，比率 ≥ 0.4 視為重複

---

## 判斷結果決策表

| 總分 | 判斷方式 | 結果 |
|------|---------|------|
| > 0.80 | 直接判定 | 重複 |
| 0.50–0.80 | LLM 判斷 | YES → 重複 / NO → 新事件 |
| < 0.50 | 直接判定 | 新事件 |

---

## 合併操作

**位置：** `backend/app/api/chat.py`，`_process_tool_use()` 函式

### 1. 觸發條件

`is_duplicate()` 對任一候選事件返回 `True` 時，取第一個匹配的事件作為合併目標（`matched_event`）。

### 2. 事件欄位更新

| 欄位 | 操作 |
|------|------|
| `report_count` | +1 |
| `severity` | `max(現有, 新通報)` |
| `casualties` | `max(現有, 新通報)` |
| `injured` | `max(現有, 新通報)` |
| `trapped` | `max(現有, 新通報)` |
| `description` | 呼叫 `merge_event_descriptions()` |
| `updated_at` | 更新為現在時間 |

所有數值欄位取較大值，確保合併後的事件反映最嚴重的已知狀況。

### 3. 描述整合 `merge_event_descriptions()`

**位置：** `backend/app/services/llm_service.py:79-103`

三條執行路徑：

| 情況 | 處理方式 |
|------|---------|
| **短路**：任一方為空，或兩者相同 | 直接返回非空的一方，不呼叫 LLM |
| **正常流程** | 呼叫 Claude Haiku（`claude-haiku-4-5-20251001`），`max_tokens=300`，限制整合描述不超過 200 字，輸出繁體中文 |
| **Fallback**：LLM 拋出例外 | 以 `f"{existing}；{new}"` 直接連接兩段描述 |

### 4. 通報關聯

新通報（`DisasterReport`）的 `event_id` 設為匹配事件的 ID，並寫入資料庫，建立通報與事件的關聯記錄。

### 5. API 回傳結構

```json
{
  "status": "merged",
  "event_id": "<UUID>",
  "message": "此通報已合併至現有事件「...」（第 N 筆通報）",
  "merged_description": "<整合後描述>",
  "geocoded_address": "<地理編碼地址>"
}
```

`status: "merged"` 與 `status: "created"` 區分新建與合併兩種結果，前端可據此顯示不同提示訊息。
