# scripts/ — 測試 DB 與測試後端輔助腳本

這個目錄放的是 **LLM E2E 測試環境**的設定與管理腳本。主系統的啟動 / 停止仍透過專案根目錄的 `start.ps1` / `stop.ps1`。

測試 DB 與生產 DB 共用同一個 Docker container（`disaster_db`），但是**不同的 database**：
- 生產：`disaster_report`
- 測試：`disaster_report_test`

測試後端跑在 **port 8001**，生產後端跑在 **port 8000**，兩個可以同時跑互不影響。

---

## 第一次使用（一次性）

確認主系統已經啟動（`disaster_db` container 在跑）：

```powershell
.\start.ps1
```

然後建立測試 DB：

```powershell
.\scripts\setup-test-db.ps1
```

這個腳本會：
1. 在 `disaster_db` container 內 `CREATE DATABASE disaster_report_test`（已存在則跳過）
2. 啟用 PostGIS extension
3. 授權 `app_user`
4. 跑 `alembic upgrade head` 套用所有 migration
5. Migration 007 會自動 seed `admin` / `admin123` 帳號

跑完後會印出 tables 清單、admin user、PostGIS 版本作為驗證。

---

## 啟動測試後端

```powershell
.\scripts\start-test-backend.ps1
```

- 在 `port 8001` 啟動 uvicorn
- `DATABASE_URL` 指向 `disaster_report_test`
- 終端標題會顯示 `TEST BACKEND :8001` 提醒目前在跑測試環境
- 開啟 http://localhost:8001/docs 可看到 Swagger UI
- 管理員登入：`admin` / `admin123`

按 `Ctrl+C` 停止。

---

## 重置測試資料

```powershell
.\scripts\reset-test-db.ps1
```

- TRUNCATE 所有 data table（`disaster_events`、`disaster_reports`、`report_attachments`、`llm_logs`）
- **保留** `users`（admin 帳號）與 `alembic_version`（schema 版本）
- 重置後 schema 不會壞，不需要重跑 migration

---

## 安全機制

| 腳本 | 防呆設計 |
|---|---|
| `setup-test-db.ps1` | DB 已存在則跳過，不會 DROP 既有資料 |
| `reset-test-db.ps1` | 硬編碼只連 `disaster_report_test`，不可能誤刪生產 DB |
| `start-test-backend.ps1` | 透過 env var 覆蓋 DATABASE_URL，不會動到 `backend\.env` |

---

## 跑 LLM E2E 測試（eval harness）

測試 DB + 測試後端就緒後，可以跑 `tests/eval/run_eval.py`：

```powershell
# 跑全部 suite（每個 case 跑前自動 reset 測試 DB，建議用於 Suite D）
backend\venv\Scripts\python.exe tests\eval\run_eval.py --reset-before-each

# 只跑某個 suite
backend\venv\Scripts\python.exe tests\eval\run_eval.py --suite a_tool_use

# 只跑單一 case
backend\venv\Scripts\python.exe tests\eval\run_eval.py --case casualty_001

# 指定後端 URL（預設 http://localhost:8001）
backend\venv\Scripts\python.exe tests\eval\run_eval.py --backend http://localhost:8001
```

報告會寫到 `tests/eval/reports/{timestamp}_summary.md`（人類閱讀）與 `_detail.json`（程式分析）。

---

## 測試 Suite 說明（共 6 個，41 個 case）

每個 suite 對應一個 YAML 檔，放在 `tests/eval/cases/`。失敗時報告會告訴你哪條 system prompt 規則沒被遵守。

### Suite A — Tool Use 欄位正確性（10 cases）
**檔案**：`suite_a_tool_use.yaml`

驗證 LLM 呼叫 `submit_disaster_report` 時填入的欄位值正確：
- 傷亡分組加總（「3 人輕傷 + 3 人重傷」必須 → `injured = 6`）
- `trapped` vs `injured` 區分（卡電梯算 trapped、等救護車算 injured）
- 死亡 vs 受傷區分（罹難算 casualties、嗆傷算 injured）
- 使用者沒提傷亡時必須填 0，不可從模糊措辭推斷
- `disaster_type` enum 映射（小型土石流 → `small_landslide`、路段崩塌 → `road_collapse`）
- `severity` 必須在 1~5 範圍內
- `occurred_at` 必須是 ISO 8601 格式

**失敗代表**：system prompt 的對應規則沒被 LLM 採用，可能要補強第 30~57 行附近的規則描述。

---

### Suite B — 時間推斷（6 cases）
**檔案**：`suite_b_time.yaml`

驗證 LLM 將相對時間轉為 ISO 8601 的能力與追問策略：
- 「半小時前」「10 分鐘前」必須推算 `now ± 容差` 內
- 「凌晨」這類模糊時段不可擅自填 04:00，必須追問
- 使用者完全沒提時間時必須追問一次（system prompt 第 43 行）
- 追問後使用者說「不知道」才可省略 `occurred_at`

**特殊機制**：使用 `within_relative` op 以「現在」為錨點，harness 與後端共用真實 `now()`，斷言可重現。

**失敗代表**：第 43 行「提交前若尚未取得發生時間必須追問一次」沒生效；或 LLM 對中文相對時間表述理解不準。

---

### Suite C — 多輪修改 / 反悔（5 cases）
**檔案**：`suite_c_revision.yaml`

驗證 LLM 在多輪對話中正確使用「最新值」，不是中間值或第一次提到的：
- 中途改地點 → `location_text` 用最新地址
- 改傷亡人數 → `injured` 用最新數字
- 改災情類型（淹水 → 火警）→ `disaster_type` 用最新
- 多輪逐步補充資訊（非修改）→ 最終欄位全對
- 改完又改回來 → 採用最後一次的值

**失敗代表**：LLM 把舊資訊與新資訊混淆，可能要在 system prompt 加入「使用者修正資訊時以最新為準」的指引。

---

### Suite D — Dedup 完整流程（5 cases）
**檔案**：`suite_d_dedup.yaml`

驗證相似事件偵測、合併、新建、resolved 過濾、相似度邊界：
- 相同地點 + 短時間 → 應觸發 `candidates_selection` SSE
- 使用者選擇合併 → `merge_event_id` 為 UUID、`db_event.report_count +1`、`injured` 被 `reextract_numbers_from_description` 重新萃取
- 使用者選擇新事件 → `merge_event_id = 'new'`、DB 多一筆
- 已結案（`resolved`）事件不應出現在候選（驗證 `find_candidate_events` 的 `status='reported'` filter）
- 相似度邊界（同類型同地點但時間隔 30 小時）→ 觸發 LLM judge

**特殊依賴**：
- 每個 case 跑前需要 `--reset-before-each`，否則種子事件會互相干擾
- 使用 `db_seed` 機制，透過 `now-30min` / `now-30hour` 等相對時間語法

**失敗代表**：
- dedup 評分邏輯偏移
- `_apply_dedup` 或 `_merge_into_event` 鏈路被破壞
- `reextract_numbers_from_description` 對合併描述的處理失準

---

### Suite E — 動態 prompt 注入（7 cases）
**檔案**：`suite_e_dynamic_prompt.yaml`

驗證 `verified_phone` / `device_location` 注入後 LLM 行為與 `_apply_verified_phone` 鏈路：
- **E-1**：`verified_phone` 注入 → LLM 整段對話不問電話、`reporter_phone` 自動覆寫
- **E-2**：`device_location` 注入 → 可推測縣市但仍會追問街道門牌
- **E-3**：兩者都帶 → 兩個邏輯都生效
- **E-4**：兩者都不帶 → 標準流程，必須問電話才能 submit
- **E-5**（攻擊測試）：`verified_phone` 衝突 — 使用者口述別的電話 → 仍以 verified 為準（防範使用者亂報、攻擊嫁禍）
- **E-6a / E-6b**（邊界測試）：`device_location` 在台灣境外（東京）或 0,0（App bug）→ LLM 不應信任 GPS、必須追問地址

**特殊斷言**：
- `all_llm_text not_contains_any` — 黑名單檢查 LLM 整段對話沒問該不該問的
- `post_apply_phone` — 從 DB 撈最新 report.reporter_phone，反映 `_apply_verified_phone` 處理後的最終值

**失敗代表**：
- E-1~E-4：`_build_system_prompt` 的動態注入沒讓 LLM 看到
- E-5：`_apply_verified_phone` 被重構錯誤或未呼叫
- E-6：`_build_system_prompt` 對 GPS 缺乏 bbox 保護，建議補上台灣 bbox 檢查

---

### Suite F — Geocoding 場景（8 cases）
**檔案**：`suite_f_geocoding.yaml`

驗證使用者描述的地點能被正確解析到台灣境內座標：
- 完整地址（縣市+區+路+號）→ 精確解析，`source` 應為 `google_places` 或 `google`
- 知名 POI（台大醫院）→ named-place fast path
- 「A 附近的 B」landmark 模式 → Step 0 兩階段查詢
- 含後綴詞（學院教室）→ `_strip_place_suffix` 處理
- 只給縣市 / 純口語模糊 → LLM 必須追問
- 連續追問仍不夠精確 → 不可直接 submit

**失敗代表**：
- Google Places / Nominatim API key 配置問題
- `_location_is_precise` 判斷邏輯偏移
- `_location_hint` 追問機制失效

---

## 相關檔案

- `backend/.env.test` — 測試環境 DATABASE_URL（供參考，實際由腳本以 env var 覆蓋）
- `tests/eval/` — automation harness 與 YAML fixtures
  - `run_eval.py` — 主 CLI 入口
  - `runner/` — SSE 解析、對話驅動、斷言 DSL、DB seed、時間 helper
  - `cases/suite_*.yaml` — 6 個 suite 共 41 個 case
  - `reports/` — 跑完後的 Markdown + JSON 報告
