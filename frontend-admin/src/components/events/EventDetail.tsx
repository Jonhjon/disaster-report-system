import { useState } from "react";
import type { DisasterEvent, DisasterReport, AttachmentOut } from "../../types";
import ImageLightbox from "./ImageLightbox";
import {
  DISASTER_TYPE_LABELS,
  SEVERITY_LABELS,
  STATUS_LABELS,
} from "../../types";
import EventEditForm from "./EventEditForm";
import { getEvents } from "../../services/api";

interface EventDetailProps {
  event: DisasterEvent;
  reports: DisasterReport[];
  onUpdate: (data: Record<string, unknown>) => Promise<void>;
  onDelete: () => Promise<void>;
  onMergeFrom: (sourceEventId: string) => Promise<void>;
}

function statusBadgeClass(status: DisasterEvent["status"]): string {
  switch (status) {
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

interface MergeModalProps {
  targetEvent: DisasterEvent;
  onConfirm: (sourceEventId: string) => Promise<void>;
  onClose: () => void;
}

function MergeModal({ targetEvent, onConfirm, onClose }: MergeModalProps) {
  const [search, setSearch] = useState("");
  const [results, setResults] = useState<DisasterEvent[]>([]);
  const [searching, setSearching] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [merging, setMerging] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSearch = async () => {
    if (!search.trim()) return;
    setSearching(true);
    setError(null);
    try {
      const resp = await getEvents({ search: search.trim(), page_size: 10 });
      setResults(resp.items.filter((e) => e.id !== targetEvent.id));
    } catch {
      setError("搜尋失敗，請稍後再試");
    } finally {
      setSearching(false);
    }
  };

  const handleConfirm = async () => {
    if (!selectedId) return;
    setMerging(true);
    setError(null);
    try {
      await onConfirm(selectedId);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "合併失敗，請稍後再試");
      setMerging(false);
    }
  };

  const selectedEvent = results.find((e) => e.id === selectedId);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="w-full max-w-lg rounded-lg bg-white p-6 shadow-xl">
        <h3 className="mb-4 text-lg font-bold">選擇要合併的來源事件</h3>
        <p className="mb-4 text-sm text-gray-500">
          選定事件的所有通報將移入「{targetEvent.title}」，來源事件將被刪除。此操作無法還原。
        </p>

        <div className="mb-4 flex gap-2">
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            placeholder="搜尋事件標題或地點..."
            className="flex-1 rounded border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <button
            onClick={handleSearch}
            disabled={searching}
            className="rounded bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {searching ? "搜尋中..." : "搜尋"}
          </button>
        </div>

        {results.length > 0 && (
          <div className="mb-4 max-h-52 overflow-y-auto rounded border">
            {results.map((ev) => (
              <button
                key={ev.id}
                type="button"
                onClick={() => setSelectedId(ev.id)}
                className={`flex w-full flex-col items-start px-3 py-2 text-left text-sm hover:bg-gray-50 ${
                  selectedId === ev.id ? "bg-blue-50" : ""
                }`}
              >
                <span className="font-medium">{ev.title}</span>
                <span className="text-xs text-gray-500">
                  {ev.location_text} · 通報數 {ev.report_count} ·{" "}
                  {DISASTER_TYPE_LABELS[ev.disaster_type]}
                </span>
              </button>
            ))}
          </div>
        )}

        {selectedEvent && (
          <div className="mb-4 rounded border border-orange-200 bg-orange-50 p-3 text-sm">
            <span className="font-semibold text-orange-800">確認合併：</span>
            <span className="text-orange-700">
              「{selectedEvent.title}」（{selectedEvent.report_count} 筆通報）將被合併入此事件並刪除。
            </span>
          </div>
        )}

        {error && (
          <p className="mb-3 text-sm text-red-600">{error}</p>
        )}

        <div className="flex justify-end gap-2">
          <button
            onClick={onClose}
            disabled={merging}
            className="rounded border px-4 py-2 text-sm hover:bg-gray-50 disabled:opacity-50"
          >
            取消
          </button>
          <button
            onClick={handleConfirm}
            disabled={!selectedId || merging}
            className="rounded bg-orange-600 px-4 py-2 text-sm text-white hover:bg-orange-700 disabled:opacity-50"
          >
            {merging ? "合併中..." : "確認合併"}
          </button>
        </div>
      </div>
    </div>
  );
}

function EventDetail({ event, reports, onUpdate, onDelete, onMergeFrom }: EventDetailProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [isConfirmingDelete, setIsConfirmingDelete] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isMergeModalOpen, setIsMergeModalOpen] = useState(false);
  const [lightboxImage, setLightboxImage] = useState<AttachmentOut | null>(null);
  const [lightboxImages, setLightboxImages] = useState<AttachmentOut[]>([]);

  return (
    <>
      {lightboxImage && (
        <ImageLightbox
          image={lightboxImage}
          images={lightboxImages}
          onClose={() => setLightboxImage(null)}
        />
      )}
      {isMergeModalOpen && (
        <MergeModal
          targetEvent={event}
          onConfirm={onMergeFrom}
          onClose={() => setIsMergeModalOpen(false)}
        />
      )}

      <div className="space-y-6">
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
                onClick={() => setIsEditing(!isEditing)}
                className="rounded-lg border px-3 py-1 text-sm hover:bg-gray-50"
              >
                {isEditing ? "取消編輯" : "編輯"}
              </button>

              <button
                onClick={() => setIsMergeModalOpen(true)}
                className="rounded-lg border border-orange-300 px-3 py-1 text-sm text-orange-600 hover:bg-orange-50"
              >
                合併事件
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
                {report.attachments && report.attachments.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-2">
                    {report.attachments.map((a) => (
                      <button
                        key={a.id}
                        title={a.original_filename}
                        className="block h-20 w-20 overflow-hidden rounded border bg-gray-100 hover:opacity-80"
                        onClick={() => {
                          setLightboxImage(a);
                          setLightboxImages(report.attachments ?? []);
                        }}
                      >
                        <img
                          src={a.url}
                          alt={a.original_filename}
                          className="h-full w-full object-cover"
                        />
                      </button>
                    ))}
                  </div>
                )}
              </div>
            ))}
            {reports.length === 0 && (
              <p className="text-sm text-gray-400">尚無通報記錄</p>
            )}
          </div>
        </div>
      </div>
    </>
  );
}

export default EventDetail;
