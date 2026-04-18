import { useCallback, useEffect, useState } from "react";
import type {
  ClarificationChannel,
  ClarificationRequest,
  DisasterEvent,
  DisasterReport,
} from "../../types";
import {
  DISASTER_TYPE_LABELS,
  MISSING_FIELD_LABELS,
  SEVERITY_LABELS,
  STATUS_LABELS,
} from "../../types";
import EventEditForm from "./EventEditForm";
import ClarificationModal from "./ClarificationModal";
import ClarificationHistoryList from "./ClarificationHistoryList";
import {
  getClarificationRequests,
  sendClarification,
} from "../../services/api";

interface EventDetailProps {
  event: DisasterEvent;
  reports: DisasterReport[];
  onUpdate: (data: Record<string, unknown>) => Promise<void>;
  onDelete: () => Promise<void>;
}

function statusBadgeClass(status: DisasterEvent["status"]): string {
  switch (status) {
    case "pending_clarification":
      return "bg-yellow-100 text-yellow-800";
    case "reported":
      return "bg-red-100 text-red-700";
    case "in_progress":
      return "bg-yellow-100 text-yellow-700";
    case "resolved":
      return "bg-green-100 text-green-700";
    default:
      return "bg-gray-100 text-gray-700";
  }
}

function CompletenessBar({
  score,
  missing,
}: {
  score: number;
  missing: string[];
}) {
  const percent = Math.round(score * 100);
  const bar =
    score >= 0.8
      ? "bg-green-500"
      : score >= 0.5
        ? "bg-yellow-500"
        : "bg-red-500";
  return (
    <div className="rounded-lg border border-gray-200 bg-gray-50 p-3">
      <div className="mb-2 flex items-center justify-between text-sm">
        <span className="font-semibold text-gray-700">資訊完整度</span>
        <span className="font-mono text-gray-600">{percent}%</span>
      </div>
      <div className="mb-2 h-2 w-full overflow-hidden rounded-full bg-gray-200">
        <div
          className={`h-full ${bar}`}
          style={{ width: `${percent}%` }}
          role="progressbar"
          aria-valuenow={percent}
          aria-valuemin={0}
          aria-valuemax={100}
        />
      </div>
      {missing.length > 0 ? (
        <div className="flex flex-wrap items-center gap-1 text-xs">
          <span className="text-gray-600">缺漏欄位：</span>
          {missing.map((f) => (
            <span
              key={f}
              className="rounded-full bg-yellow-100 px-2 py-0.5 text-yellow-800"
            >
              {MISSING_FIELD_LABELS[f] ?? f}
            </span>
          ))}
        </div>
      ) : (
        <p className="text-xs text-green-700">✓ 所有關鍵欄位皆已齊備</p>
      )}
    </div>
  );
}

function EventDetail({ event, reports, onUpdate, onDelete }: EventDetailProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [isConfirmingDelete, setIsConfirmingDelete] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  const [modalOpen, setModalOpen] = useState(false);
  const [clarifications, setClarifications] = useState<ClarificationRequest[]>(
    []
  );
  const [loadingClarifications, setLoadingClarifications] = useState(false);
  const [clarifError, setClarifError] = useState<string | null>(null);

  const latestReport = reports.length > 0 ? reports[0] : null;

  const refreshClarifications = useCallback(async () => {
    setLoadingClarifications(true);
    setClarifError(null);
    try {
      const resp = await getClarificationRequests(event.id);
      setClarifications(resp.items);
    } catch (err) {
      setClarifError(err instanceof Error ? err.message : "載入失敗");
    } finally {
      setLoadingClarifications(false);
    }
  }, [event.id]);

  useEffect(() => {
    refreshClarifications();
  }, [refreshClarifications]);

  const handleSubmitClarification = async (data: {
    question: string;
    channel: ClarificationChannel;
    recipient?: string;
  }) => {
    await sendClarification(event.id, data);
    await refreshClarifications();
  };

  return (
    <div className="space-y-6">
      {/* Event info card */}
      <div className="rounded-lg border bg-white p-6">
        <div className="mb-4 flex items-start justify-between">
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-xl font-bold">{event.title}</h2>
              <span
                className={`rounded-full px-2 py-0.5 text-xs font-semibold ${statusBadgeClass(event.status)}`}
              >
                {STATUS_LABELS[event.status]}
              </span>
            </div>
            <p className="text-sm text-gray-500">
              建立於 {new Date(event.created_at).toLocaleString("zh-TW")} | 最後更新{" "}
              {new Date(event.updated_at).toLocaleString("zh-TW")}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setModalOpen(true)}
              className="rounded-lg border border-yellow-400 bg-yellow-50 px-3 py-1 text-sm font-semibold text-yellow-800 hover:bg-yellow-100"
            >
              📨 發送追問
            </button>
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

        {event.completeness && (
          <div className="mb-4">
            <CompletenessBar
              score={event.completeness.score}
              missing={event.completeness.missing}
            />
          </div>
        )}

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

      {/* Clarification history */}
      <div className="rounded-lg border bg-white p-6">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-bold">追問紀錄</h3>
          <button
            onClick={refreshClarifications}
            className="text-sm text-blue-600 hover:underline"
          >
            重新整理
          </button>
        </div>
        {clarifError && (
          <p className="mb-3 rounded bg-red-50 px-3 py-2 text-sm text-red-700">
            {clarifError}
          </p>
        )}
        <ClarificationHistoryList
          items={clarifications}
          loading={loadingClarifications}
        />
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

      <ClarificationModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onSubmit={handleSubmitClarification}
        latestReport={latestReport}
        completeness={event.completeness}
      />
    </div>
  );
}

export default EventDetail;
