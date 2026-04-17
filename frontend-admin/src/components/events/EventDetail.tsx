import { useState } from "react";
import type { DisasterEvent, DisasterReport } from "../../types";
import {
  DISASTER_TYPE_LABELS,
  SEVERITY_LABELS,
  STATUS_LABELS,
} from "../../types";
import EventEditForm from "./EventEditForm";

interface EventDetailProps {
  event: DisasterEvent;
  reports: DisasterReport[];
  onUpdate: (data: Record<string, unknown>) => Promise<void>;
  onDelete: () => Promise<void>;
}

function EventDetail({ event, reports, onUpdate, onDelete }: EventDetailProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [isConfirmingDelete, setIsConfirmingDelete] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  return (
    <div className="space-y-6">
      {/* Event info card */}
      <div className="rounded-lg border bg-white p-6">
        <div className="mb-4 flex items-start justify-between">
          <div>
            <h2 className="text-xl font-bold">{event.title}</h2>
            <p className="text-sm text-gray-500">
              建立於 {new Date(event.created_at).toLocaleString("zh-TW")} | 最後更新{" "}
              {new Date(event.updated_at).toLocaleString("zh-TW")}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setIsEditing(!isEditing)}
              className="rounded-lg border px-3 py-1 text-sm hover:bg-gray-50"
            >
              {isEditing ? "取消編輯" : "編輯"}
            </button>

            {!isConfirmingDelete ? (
              <button
                onClick={() => setIsConfirmingDelete(true)}
                className="rounded-lg border border-red-300 px-3 py-1 text-sm text-red-600 hover:bg-red-50"
              >
                刪除
              </button>
            ) : (
              <div className="flex items-center gap-2">
                <span className="text-sm text-gray-600">確定刪除？</span>
                <button
                  onClick={async () => {
                    setIsDeleting(true);
                    try {
                      await onDelete();
                    } finally {
                      setIsDeleting(false);
                      setIsConfirmingDelete(false);
                    }
                  }}
                  disabled={isDeleting}
                  className="rounded-lg bg-red-600 px-3 py-1 text-sm text-white hover:bg-red-700 disabled:opacity-50"
                >
                  {isDeleting ? "刪除中..." : "確定"}
                </button>
                <button
                  onClick={() => setIsConfirmingDelete(false)}
                  className="rounded-lg border px-3 py-1 text-sm hover:bg-gray-50"
                >
                  取消
                </button>
              </div>
            )}
          </div>
        </div>

        {isEditing ? (
          <EventEditForm
            event={event}
            onSave={async (data) => {
              await onUpdate(data);
              setIsEditing(false);
            }}
            onCancel={() => setIsEditing(false)}
          />
        ) : (
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <span className="text-gray-500">災情種類：</span>
              <span className="font-medium">
                {DISASTER_TYPE_LABELS[event.disaster_type]}
              </span>
            </div>
            <div>
              <span className="text-gray-500">嚴重程度：</span>
              <span className="font-medium">
                {event.severity} - {SEVERITY_LABELS[event.severity]}
              </span>
            </div>
            <div>
              <span className="text-gray-500">狀態：</span>
              <span className="font-medium">
                {STATUS_LABELS[event.status]}
              </span>
            </div>
            <div>
              <span className="text-gray-500">通報數量：</span>
              <span className="font-medium">{event.report_count}</span>
            </div>
            <div className="col-span-2">
              <span className="text-gray-500">地點：</span>
              <span className="font-medium">
                {(() => {
                  const full = reports[0]?.geocoded_address;
                  if (full && full !== event.location_text) {
                    return `${full}（${event.location_text}）`;
                  }
                  return event.location_text;
                })()}
              </span>
            </div>
            <div>
              <span className="text-gray-500">發生時間：</span>
              <span className="font-medium">
                {new Date(event.occurred_at).toLocaleString("zh-TW")}
              </span>
            </div>
            <div>
              <span className="text-gray-500">死亡：</span>
              <span className="font-medium">{event.casualties}</span>
            </div>
            <div>
              <span className="text-gray-500">受傷：</span>
              <span className="font-medium">{event.injured}</span>
            </div>
            <div>
              <span className="text-gray-500">受困：</span>
              <span className="font-medium">{event.trapped}</span>
            </div>
            <div className="col-span-2">
              <span className="text-gray-500">描述：</span>
              <p className="mt-1 whitespace-pre-wrap font-medium">
                {event.description || "（無描述）"}
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Related reports */}
      <div className="rounded-lg border bg-white p-6">
        <h3 className="mb-4 text-lg font-bold">
          相關通報（{reports.length} 筆）
        </h3>
        <div className="space-y-3">
          {reports.map((report) => (
            <div key={report.id} className="rounded border p-3">
              <div className="mb-1 flex items-center gap-2 text-xs text-gray-500">
                <span>
                  {new Date(report.created_at).toLocaleString("zh-TW")}
                </span>
                {report.reporter_name && (
                  <span>通報者：{report.reporter_name}</span>
                )}
              </div>
              <p className="whitespace-pre-wrap text-sm">{report.raw_message}</p>
            </div>
          ))}
          {reports.length === 0 && (
            <p className="text-sm text-gray-400">尚無通報記錄</p>
          )}
        </div>
      </div>
    </div>
  );
}

export default EventDetail;
