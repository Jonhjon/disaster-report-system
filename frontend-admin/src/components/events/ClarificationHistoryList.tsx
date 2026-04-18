import type { ClarificationRequest } from "../../types";
import {
  CLARIFICATION_CHANNEL_LABELS,
  CLARIFICATION_STATUS_LABELS,
} from "../../types";

interface ClarificationHistoryListProps {
  items: ClarificationRequest[];
  loading?: boolean;
}

function statusStyle(status: ClarificationRequest["status"]): string {
  switch (status) {
    case "replied":
      return "bg-green-100 text-green-800";
    case "delivered":
      return "bg-blue-100 text-blue-800";
    case "sent":
      return "bg-cyan-100 text-cyan-800";
    case "failed":
      return "bg-red-100 text-red-800";
    default:
      return "bg-gray-100 text-gray-700";
  }
}

function formatTime(iso: string | null): string {
  if (!iso) return "-";
  return new Date(iso).toLocaleString("zh-TW");
}

function ClarificationHistoryList({
  items,
  loading,
}: ClarificationHistoryListProps) {
  if (loading) {
    return <p className="text-sm text-gray-400">載入中...</p>;
  }
  if (!items.length) {
    return <p className="text-sm text-gray-400">尚無追問紀錄</p>;
  }
  return (
    <div className="space-y-3">
      {items.map((item) => (
        <div key={item.id} className="rounded-lg border border-gray-200 p-3">
          <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-gray-500">
            <span>📤 {formatTime(item.created_at)}</span>
            <span className="rounded bg-gray-100 px-2 py-0.5 text-gray-700">
              {CLARIFICATION_CHANNEL_LABELS[item.channel]}
            </span>
            <span className="text-gray-700">→ {item.recipient}</span>
            <span
              className={`ml-auto rounded-full px-2 py-0.5 font-semibold ${statusStyle(item.status)}`}
            >
              {CLARIFICATION_STATUS_LABELS[item.status]}
            </span>
          </div>
          <p className="whitespace-pre-wrap text-sm text-gray-800">
            {item.question}
          </p>
          <div className="mt-2 grid grid-cols-3 gap-2 text-xs text-gray-500">
            <div>送達：{formatTime(item.delivered_at)}</div>
            <div>回覆：{formatTime(item.replied_at)}</div>
            <div>發送：{formatTime(item.sent_at)}</div>
          </div>
          {item.error_message && (
            <p className="mt-2 rounded bg-red-50 px-2 py-1 text-xs text-red-700">
              錯誤：{item.error_message}
            </p>
          )}
        </div>
      ))}
    </div>
  );
}

export default ClarificationHistoryList;
