# E2E 測試資料：通報案例集

本文件提供涵蓋「所有事件可能」的 E2E 測試資料，分三類：

- **A 類 — 核心矩陣**：9 種災害類型 × severity 1~5。
- **B 類 — 特殊流程**：合併、地址消歧義、精確度追問、時間未知/概略、附件、已驗證電話。
- **C 類 — 邊界／防呆**：重傷子集、使用者自報嚴重度、分組傷者加總等。

A 類與 C 類為「單輪即可提交」的通報，已轉成可自動化的資料檔與參數化測試；
B 類需多輪/DB seed/mock，已由既有確定性測試覆蓋（見 §B）。

> **資料檔（單一事實來源）**：`backend/tests/e2e/e2e_report_cases.json`
> **參數化測試**：`backend/tests/e2e/test_e2e_report_extraction.py`
> **分級規則**：見 [severity-rules.md](./severity-rules.md)

---

## 如何執行自動化

```bash
cd backend
# 需真實 Anthropic API；-s 才看得到每筆即時輸出
RUN_LLM_EVALS=1 pytest tests/e2e -m llm -s
```

- 未設 `RUN_LLM_EVALS=1` 時全部 **skip**（CI 預設不呼叫 API）。
- 每筆會即時（`flush=True`）印出：`▶ 開始` → `擷取結果` → `✔ 通過`。
- **severity 為 LLM 即時推斷、非完全確定性**：擷取欄位（類型/傷亡數字）採 exact 比對，
  severity 預設容忍 **±1**（案例可用 `severity_tolerance` 覆寫，明確案例設 0）。
- **最新驗證結果：24 筆全數通過**（2026-08）。

---

## A 類：核心矩陣（9 類型 × severity 1~5）

每則輸入都寫成「資訊齊全」（含地點門牌、時間、姓名電話、明確傷亡）以便一次提交；
若缺料，LLM 會依對話協定改為追問。

| ID | severity | 類型 | 通報輸入摘要 | 期望擷取（傷亡：死/傷/重傷/困） | 涵蓋重點 |
|----|:---:|------|--------------|------------------------------|---------|
| A1 | 1 | small_landslide | 北宜路二段45號旁邊坡少量落石，無傷亡 | 0/0/0/0 | small_landslide 保底=1 |
| A2 | 1 | utility_damage | 和平東路一段20號路燈電線吹落，無傷 | 0/0/0/0 | utility 保底=1 |
| A3 | 1 | other | 中央路100號路樹倒塌擋道，無傷亡 | 0/0/0/0 | other 保底=1 |
| A4 | 2 | fire | 民生路50號住家廚房失火已撲滅，無傷 | 0/0/0/0 | fire 基準=2、無關鍵字 |
| A5 | 2 | road_collapse | 林森路一段88號路面塌陷大洞，無傷 | 0/0/0/0 | road_collapse 基準=2 |
| A6 | 2 | flooding | 四維三路30號巷口積水10公分，無傷亡 | 0/0/0/0 | flooding 基準=2、小範圍 |
| A7 | 2 | small_landslide | 中山路三段12號後小型土石流，2人擦傷 | 0/2/0/0 | 輕傷 1–4 → L_cas 2 |
| A8 | 2 | building_damage | 愛四路5號老屋外牆磁磚剝落，無傷 | 0/0/0/0 | building 基準=2 |
| A9 | 2 | utility_damage | 木新路整區大規模停電數千戶，無傷亡 | 0/0/0/0 | utility 1 +「大規模」+1 |
| A10 | 3 | trapped | 文化路一段25號1人受困電梯待救 | 0/0/0/1 | trapped 基準=3 / 受困 1–2 |
| A11 | 3 | flooding | 中山路二段整條路大範圍淹水及腰，無傷亡 | 0/0/0/0 | flooding 2 +「大範圍」+1 |
| A12 | 3 | landslide | 台11線35K 土石流沖入農地，無傷 | 0/0/0/0 | landslide 基準=3 |
| A13 | 3 | utility_damage | 學士路60號瓦斯管線破裂大量外洩，無傷 | 0/0/0/0 | 關鍵字「瓦斯外洩」floor 3 |
| A14 | 4 | fire | 松仁路100號工廠火警延燒，5傷其中2重傷 | 0/5/2/0 | 重傷 1–2 → L_cas 3 +「延燒」+1 |
| A15 | 4 | road_collapse | 台9線120K 路面坍方，車陷落3人受困待救 | 0/0/0/3 | 受困 3–7 → L_cas 4 |
| A16 | 4 | landslide | 台9線118K 土石流沖入民宅致1死 | 1/0/0/0 | 死亡 1–2 → L_cas 4 |
| A17 | 5 | fire | 大同路8號工廠氣爆起火，3死8傷5重傷3困 | 3/8/5/3 | 死亡 ≥3 → 5；含氣爆 |
| A18 | 5 | trapped | 南京東路三段200號商場坍塌，約10人受困待救 | 0/0/0/10 | 受困 ≥8 → 5 |
| A19 | 5 | building_damage | 中正路512號公寓整棟倒塌，3死2受困 | 3/0/0/2 | 死亡 ≥3 → 5；整棟倒塌 floor 4 |

> 完整輸入文字見 `e2e_report_cases.json`。

---

## B 類：特殊流程（已由既有確定性測試覆蓋）

這些流程需要多輪對話、DB 種子或 mock，**不在 LLM eval 內重複**；對應的既有測試如下：

| 流程 | 情境 | 既有測試 |
|------|------|---------|
| 事件合併 / 去重 | 同地點二次通報 → 合併、severity 取 max、傷亡 reextract 累計 | `tests/test_merge_event.py`、`tests/test_dedup_disambiguation.py`、`tests/test_merge_race_condition.py` |
| 地址消歧義 | 連鎖店名有多分店 → 回傳候選要使用者選 | `tests/test_dedup_flow.py`（`candidates_selection`） |
| 地點精確度追問 | 只給區/路名無門牌 → 系統追問 | `tests/test_location_precision.py`、`tests/test_location_hint.py` |
| 發生時間未知/概略 | 「不知道時間」→ 省略；「大概昨晚」→ approximate | `tests/test_chat_occurred_at_approximate.py` |
| 附件綁定 | 通報附現場照片 | `tests/test_chat_with_attachments.py` |
| 已驗證電話（行動 App） | 帶 verified_phone → 不再問電話 | `tests/test_chat_verified_phone.py` |
| 錯誤回滾 | stream 例外 → db.rollback | `tests/test_chat_rollback_on_error.py` |

若要為 B 類新增「自然語言輸入」層級的 E2E，建議以 `test_dedup_flow.py` 的
`mock_stream_chat` + `parse_sse_events` 為骨架擴充。

---

## C 類：邊界／防呆（已納入自動化）

| ID | severity | 通報輸入摘要 | 期望 | 涵蓋重點 |
|----|:---:|--------------|------|---------|
| C1 | 4 | 辦公大樓外牆倒塌砸傷，10傷其中4重傷，無死無困 | injured=10, severe=4 | 重傷是子集(severe≤injured)、重傷 3–7 → L_cas 4 |
| C2 | 2 | 「幫我打10級！」住家廚房小火，無傷 | fire, severity=2 | 不採信使用者自報嚴重度 |
| C3 | 2 | 建物火警，明講無人死傷受困 | 全 0 | 明確 0 與未提及都視為 0 |
| C4 | 3 | 民宅氣爆，死傷不明 | severity=3 | 傷亡未知時「氣爆」floor 3 撐底（類型可能 fire/building/other） |
| C5 | 3 | 餐廳火警，5輕傷3中傷2重傷 | injured=10, severe=2 | 分組傷者加總、severe 只填重傷組 |

---

## 使用注意

1. **輸入須資訊齊全才會一次提交**：地點（門牌/路名/里程）、時間、姓名電話、明確傷亡人數缺一，
   LLM 可能改為追問，`_extract` 會回 `None`（測試視為失敗，訊息會提示「被追問」）。
2. **災害類型措辭要精準**：例如「邊坡崩塌」會被判為 `landslide`，要 `road_collapse` 需用
   「路面坍方/道路坍塌」等字眼。
3. **severity 容忍 ±1**：LLM 非確定性，關鍵字加權案例尤其可能 ±1；明確人數案例（如 A17~A19）
   設 `severity_tolerance: 0`。
4. **修改測資** 只需編輯 `e2e_report_cases.json`，測試會自動帶入（參數化 id = 案例 id）。
