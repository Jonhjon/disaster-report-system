import { DISASTER_TYPE_LABELS, DISASTER_TYPE_COLORS, DisasterType } from "../types/index";

function HelpPage() {
  const disasterTypes = Object.keys(DISASTER_TYPE_LABELS) as DisasterType[];

  return (
    <div className="mx-auto max-w-3xl space-y-6 py-4">
      <h1 className="text-2xl font-bold text-gray-800">使用說明</h1>

      <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
        <h2 className="mb-3 text-lg font-semibold text-gray-800">
          <span className="mr-2">🏠</span>系統介紹
        </h2>
        <p className="mb-2 text-sm text-gray-700">
          <strong>智慧災害通報系統 — 管理中心</strong>
          提供救災人員與管理者完整的災情管理功能，包含事件查看、編輯、狀態更新及 LLM 呼叫監控。
        </p>
      </div>

      <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
        <h2 className="mb-3 text-lg font-semibold text-gray-800">
          <span className="mr-2">🗺</span>地圖總覽
        </h2>
        <p className="mb-3 text-sm text-gray-700">
          地圖上的色點代表各災情事件，不同顏色對應不同災情類型：
        </p>
        <div className="mb-4 grid grid-cols-2 gap-2">
          {disasterTypes.map((type) => (
            <div key={type} className="flex items-center gap-2 text-sm text-gray-700">
              <span
                className="inline-block h-4 w-4 flex-shrink-0 rounded-full"
                style={{ backgroundColor: DISASTER_TYPE_COLORS[type] }}
              />
              {DISASTER_TYPE_LABELS[type]}
            </div>
          ))}
        </div>
      </div>

      <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
        <h2 className="mb-3 text-lg font-semibold text-gray-800">
          <span className="mr-2">📋</span>災情列表
        </h2>
        <ul className="ml-4 list-disc space-y-2 text-sm text-gray-700">
          <li>
            <span className="font-medium">搜尋與篩選</span>：可依關鍵字、災情類型、事件狀態快速過濾列表。
          </li>
          <li>
            <span className="font-medium">排序</span>：支援依時間、嚴重程度排序，預設顯示最新事件。
          </li>
          <li>
            <span className="font-medium">查看詳情</span>：點擊任一事件，進入詳細頁面查看完整資訊。
          </li>
          <li>
            <span className="font-medium">編輯與刪除</span>：在詳細頁面可更新事件狀態、傷亡人數，或刪除事件。
          </li>
        </ul>
      </div>

      <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
        <h2 className="mb-3 text-lg font-semibold text-gray-800">
          <span className="mr-2">📊</span>LLM 日誌
        </h2>
        <p className="text-sm text-gray-700">
          顯示最近 100 筆 AI 模型呼叫紀錄，包含模型名稱、延遲、token 用量及狀態。可展開查看完整 prompt 和回應內容，用於監控系統運作狀況。
        </p>
      </div>
    </div>
  );
}

export default HelpPage;
