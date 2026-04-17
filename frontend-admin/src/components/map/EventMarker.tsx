import { useState } from "react";
import { CircleMarker, Popup } from "react-leaflet";
import { Link } from "react-router-dom";
import type { EventMapItem } from "../../types";
import {
  DISASTER_TYPE_LABELS,
  DISASTER_TYPE_COLORS,
  SEVERITY_LABELS,
} from "../../types";
import { updateEventLocation } from "../../services/api";

function EventMarker({
  event,
  onLocationUpdated,
}: {
  event: EventMapItem;
  onLocationUpdated?: (updated: EventMapItem) => void;
}) {
  const color = DISASTER_TYPE_COLORS[event.disaster_type] || "#95a5a6";
  const radius = 6 + event.severity * 2;
  const [editing, setEditing] = useState(false);
  const [newAddress, setNewAddress] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!newAddress.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      const updated = await updateEventLocation(event.id, newAddress.trim());
      setEditing(false);
      setNewAddress("");
      onLocationUpdated?.(updated);
    } catch {
      setError("無法辨識此地址，請輸入更具體的地點");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <CircleMarker
      center={[event.latitude, event.longitude]}
      radius={radius}
      fillColor={color}
      color={color}
      weight={2}
      opacity={0.8}
      fillOpacity={0.5}
    >
      <Popup>
        <div className="min-w-48">
          <h3 className="mb-1 text-sm font-bold">{event.title}</h3>
          <div className="space-y-1 text-xs text-gray-600">
            <p>
              類型：{DISASTER_TYPE_LABELS[event.disaster_type]}
            </p>
            <p>
              嚴重程度：{SEVERITY_LABELS[event.severity]}（{event.severity}/5）
            </p>
            <p>通報數：{event.report_count}</p>
            <p>
              時間：{new Date(event.occurred_at).toLocaleString("zh-TW")}
            </p>
          </div>
          {event.location_approximate && (
            <div className="mt-2 rounded border border-yellow-400 bg-yellow-50 p-2 text-xs">
              <p className="font-semibold text-yellow-700">⚠ 位置為估算，可能不準確</p>
              {editing ? (
                <form onSubmit={handleSubmit} className="mt-1 space-y-1">
                  <input
                    className="w-full rounded border border-gray-300 px-1 py-0.5 text-xs"
                    placeholder="輸入正確地址（縣市＋區＋路段）"
                    value={newAddress}
                    onChange={(e) => setNewAddress(e.target.value)}
                    disabled={submitting}
                  />
                  {error && <p className="text-red-600">{error}</p>}
                  <div className="flex gap-1">
                    <button
                      type="submit"
                      disabled={submitting || !newAddress.trim()}
                      className="rounded bg-blue-600 px-2 py-0.5 text-white disabled:opacity-50"
                    >
                      {submitting ? "處理中…" : "確認修正"}
                    </button>
                    <button
                      type="button"
                      onClick={() => { setEditing(false); setError(null); }}
                      className="rounded border px-2 py-0.5"
                    >
                      取消
                    </button>
                  </div>
                </form>
              ) : (
                <button
                  onClick={() => setEditing(true)}
                  className="mt-1 rounded bg-yellow-600 px-2 py-0.5 text-white text-xs"
                >
                  修正地址
                </button>
              )}
            </div>
          )}
          <Link
            to={`/events/${event.id}`}
            className="mt-2 inline-block text-xs text-blue-600 hover:underline"
          >
            查看詳情
          </Link>
        </div>
      </Popup>
    </CircleMarker>
  );
}

export default EventMarker;
