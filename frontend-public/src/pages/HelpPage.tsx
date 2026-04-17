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
          <strong>智慧災害通報系統</strong>
          讓民眾能透過自然語言對話，快速通報地震、颱風、水災等各類災情。系統由 AI 自動擷取結構化資訊，並即時顯示在地圖上，協助救災人員掌握現場狀況。
        </p>
        <ul className="ml-4 list-disc space-y-1 text-sm text-gray-700">
          <li>支援 8 種災情類型自動辨識</li>
          <li>即時地圖標記，快速掌握受災分布</li>
          <li>適合民眾、里長、救災志工等各類通報者使用</li>
        </ul>
      </div>

      <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
        <h2 className="mb-3 text-lg font-semibold text-gray-800">
          <span className="mr-2">📢</span>如何通報災情
        </h2>
        <ol className="ml-4 list-decimal space-y-3 text-sm text-gray-700">
          <li>
            <span className="font-medium">點選左側「📢 通報災情」</span>
            ，進入通報頁面。
          </li>
          <li>
            <span className="font-medium">與 AI 助理對話</span>
            ，用自然語言描述現場狀況，例如：
            <br />
            <span className="mt-1 inline-block rounded bg-gray-100 px-2 py-1 font-mono text-xs text-gray-600">
              「台北市信義區仁愛路四段發生淹水，積水約50公分，有3人受困」
            </span>
          </li>
          <li>
            <span className="font-medium">系統自動建立通報</span>
            ，AI 會擷取地點、災情類型、傷亡人數等資訊，並在地圖上標記。
          </li>
        </ol>
        <p className="mt-3 text-xs text-gray-500">
          提示：描述越詳細（地址、傷亡、狀況），AI 擷取的資訊越準確。
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
        <p className="text-sm text-gray-700">
          地圖右上角可依<span className="font-medium">災情類型</span>或
          <span className="font-medium">事件狀態</span>篩選，點擊色點可查看事件摘要。
        </p>
      </div>
    </div>
  );
}

export default HelpPage;
