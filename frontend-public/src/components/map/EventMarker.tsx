import { CircleMarker, Popup } from "react-leaflet";
import type { EventMapItem } from "../../types";
import {
  DISASTER_TYPE_LABELS,
  DISASTER_TYPE_COLORS,
  SEVERITY_LABELS,
} from "../../types";

function EventMarker({ event }: { event: EventMapItem }) {
  const color = DISASTER_TYPE_COLORS[event.disaster_type] || "#95a5a6";
  const radius = 6 + event.severity * 2;

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
            <p>類型：{DISASTER_TYPE_LABELS[event.disaster_type]}</p>
            <p>嚴重程度：{SEVERITY_LABELS[event.severity]}（{event.severity}/5）</p>
            <p>通報數：{event.report_count}</p>
            <p>時間：{new Date(event.occurred_at).toLocaleString("zh-TW")}</p>
          </div>
          {event.location_approximate && (
            <p className="mt-2 text-xs font-semibold text-yellow-700">
              ⚠ 位置為估算，可能不準確
            </p>
          )}
        </div>
      </Popup>
    </CircleMarker>
  );
}

export default EventMarker;
