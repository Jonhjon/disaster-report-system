import { Link } from "react-router-dom";
import type { DisasterEvent } from "../../types";
import {
  DISASTER_TYPE_LABELS,
  SEVERITY_LABELS,
  STATUS_LABELS,
  DISASTER_TYPE_COLORS,
} from "../../types";

interface EventTableProps {
  events: DisasterEvent[];
  page: number;
  totalPages: number;
  onPageChange: (page: number) => void;
}

function EventTable({ events, page, totalPages, onPageChange }: EventTableProps) {
  return (
    <div className="overflow-hidden rounded-lg border bg-white">
      <table className="w-full text-left text-sm">
        <thead className="border-b bg-gray-50 text-xs uppercase text-gray-500">
          <tr>
            <th className="px-4 py-3">災情種類</th>
            <th className="px-4 py-3">標題</th>
            <th className="px-4 py-3">地點</th>
            <th className="px-4 py-3">嚴重程度</th>
            <th className="px-4 py-3">狀態</th>
            <th className="px-4 py-3">通報數</th>
            <th className="px-4 py-3">發生時間</th>
            <th className="px-4 py-3">操作</th>
          </tr>
        </thead>
        <tbody>
          {events.map((event) => (
            <tr key={event.id} className="border-b hover:bg-gray-50">
              <td className="px-4 py-3">
                <span
                  className="inline-block rounded-full px-2 py-1 text-xs font-semibold text-white"
                  style={{
                    backgroundColor:
                      DISASTER_TYPE_COLORS[event.disaster_type] || "#95a5a6",
                  }}
                >
                  {DISASTER_TYPE_LABELS[event.disaster_type]}
                </span>
              </td>
              <td className="px-4 py-3 font-medium">{event.title}</td>
              <td className="px-4 py-3 text-gray-600">{event.location_text}</td>
              <td className="px-4 py-3">
                <span
                  className={`font-semibold ${
                    event.severity >= 4
                      ? "text-red-600"
                      : event.severity >= 3
                        ? "text-orange-500"
                        : "text-yellow-600"
                  }`}
                >
                  {event.severity} - {SEVERITY_LABELS[event.severity]}
                </span>
              </td>
              <td className="px-4 py-3">
                <span
                  className={`rounded-full px-2 py-1 text-xs ${
                    event.status === "active"
                      ? "bg-red-100 text-red-700"
                      : event.status === "monitoring"
                        ? "bg-yellow-100 text-yellow-700"
                        : "bg-green-100 text-green-700"
                  }`}
                >
                  {STATUS_LABELS[event.status]}
                </span>
              </td>
              <td className="px-4 py-3">{event.report_count}</td>
              <td className="px-4 py-3 text-gray-600">
                {new Date(event.occurred_at).toLocaleString("zh-TW")}
              </td>
              <td className="px-4 py-3">
                <Link
                  to={`/events/${event.id}`}
                  className="text-blue-600 hover:underline"
                >
                  詳情
                </Link>
              </td>
            </tr>
          ))}
          {events.length === 0 && (
            <tr>
              <td colSpan={8} className="px-4 py-8 text-center text-gray-400">
                沒有找到符合條件的災情事件
              </td>
            </tr>
          )}
        </tbody>
      </table>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between border-t px-4 py-3">
          <button
            onClick={() => onPageChange(page - 1)}
            disabled={page <= 1}
            className="rounded border px-3 py-1 text-sm disabled:opacity-50"
          >
            上一頁
          </button>
          <span className="text-sm text-gray-600">
            第 {page} / {totalPages} 頁
          </span>
          <button
            onClick={() => onPageChange(page + 1)}
            disabled={page >= totalPages}
            className="rounded border px-3 py-1 text-sm disabled:opacity-50"
          >
            下一頁
          </button>
        </div>
      )}
    </div>
  );
}

export default EventTable;
