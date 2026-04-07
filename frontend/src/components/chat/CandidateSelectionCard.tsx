import type { EventCandidate } from "../../types";

interface CandidateSelectionCardProps {
  candidates: EventCandidate[];
  onSelect: (eventId: string) => void;
}

function CandidateSelectionCard({ candidates, onSelect }: CandidateSelectionCardProps) {
  return (
    <div className="mx-2 my-3">
      <p className="mb-2 text-xs font-semibold text-gray-500 uppercase tracking-wide">
        系統偵測到相似事件，請選擇：
      </p>
      <div className="flex flex-col gap-2">
        {candidates.map((c) => (
          <button
            key={c.event_id}
            onClick={() => onSelect(c.event_id)}
            className="w-full rounded-lg border border-orange-200 bg-orange-50 px-4 py-3 text-left text-sm hover:border-orange-400 hover:bg-orange-100 transition-colors focus:outline-none focus:ring-2 focus:ring-orange-400"
          >
            <div className="font-semibold text-gray-800">{c.title}</div>
            <div className="mt-0.5 text-gray-600 text-xs">{c.location_text}</div>
            <div className="mt-1.5 flex flex-wrap gap-2 text-xs text-gray-500">
              <span className="rounded bg-white px-1.5 py-0.5 border border-gray-200">
                距離 {c.distance_m} 公尺
              </span>
              <span className="rounded bg-white px-1.5 py-0.5 border border-gray-200">
                相似度 {Math.round(c.score * 100)}%
              </span>
              <span className="rounded bg-white px-1.5 py-0.5 border border-gray-200">
                {c.report_count} 筆通報
              </span>
            </div>
          </button>
        ))}

        {/* 建立新事件 永遠顯示在最後 */}
        <button
          onClick={() => onSelect("new")}
          className="w-full rounded-lg border border-gray-200 bg-gray-50 px-4 py-3 text-left text-sm hover:border-gray-400 hover:bg-gray-100 transition-colors focus:outline-none focus:ring-2 focus:ring-gray-400"
        >
          <div className="font-semibold text-gray-700">建立新事件</div>
          <div className="mt-0.5 text-xs text-gray-500">此通報與上述事件無關</div>
        </button>
      </div>
    </div>
  );
}

export default CandidateSelectionCard;
