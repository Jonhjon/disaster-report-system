import { useNavigate } from "react-router-dom";
import {
  useNotifications,
  type NotificationItem,
} from "../../contexts/NotificationContext";
import { DISASTER_TYPE_LABELS, SEVERITY_LABELS } from "../../types";
import { isDisasterType } from "../../utils/disasterType";

interface Props {
  onClose: () => void;
}

const SEVERITY_BG: Record<number, string> = {
  1: "bg-gray-100 text-gray-700",
  2: "bg-yellow-100 text-yellow-800",
  3: "bg-orange-100 text-orange-800",
  4: "bg-red-100 text-red-800",
  5: "bg-red-200 text-red-900",
};

function relativeTime(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  if (diffMs < 0) return "剛剛";
  const sec = Math.floor(diffMs / 1000);
  if (sec < 60) return `${sec} 秒前`;
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min} 分鐘前`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr} 小時前`;
  const day = Math.floor(hr / 24);
  return `${day} 天前`;
}

function disasterLabel(type: string): string {
  if (isDisasterType(type)) return DISASTER_TYPE_LABELS[type];
  return type;
}

function NotificationRow({
  item,
  onClick,
}: {
  item: NotificationItem;
  onClick: () => void;
}) {
  const severityClass = SEVERITY_BG[item.severity] ?? SEVERITY_BG[3];
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex w-full flex-col items-start gap-1 border-b px-3 py-2 text-left hover:bg-gray-50 ${
        item.read ? "opacity-60" : ""
      }`}
    >
      <div className="flex w-full items-center justify-between gap-2">
        <span className="line-clamp-1 text-sm font-medium text-gray-900">
          {item.title}
        </span>
        <div className="flex shrink-0 items-center gap-1">
          {item.possible_duplicate_event_id && (
            <span className="rounded bg-orange-100 px-1.5 py-0.5 text-xs font-semibold text-orange-700">
              ⚠ 可能重複
            </span>
          )}
          {!item.read && (
            <span className="h-2 w-2 rounded-full bg-blue-500" />
          )}
        </div>
      </div>
      <div className="flex w-full items-center gap-2 text-xs text-gray-600">
        <span className={`rounded px-1.5 py-0.5 ${severityClass}`}>
          {SEVERITY_LABELS[item.severity] ?? `等級 ${item.severity}`}
        </span>
        <span>{disasterLabel(item.disaster_type)}</span>
        <span className="line-clamp-1 flex-1 text-gray-500">
          {item.location_text}
        </span>
        <span className="text-gray-400">{relativeTime(item.received_at)}</span>
      </div>
    </button>
  );
}

function NotificationPanel({ onClose }: Props) {
  const { notifications, unreadCount, markAllRead, markRead } =
    useNotifications();
  const navigate = useNavigate();

  const handleSelect = (item: NotificationItem) => {
    markRead(item.event_id);
    onClose();
    navigate(`/events/${item.event_id}`);
  };

  return (
    <div className="absolute right-0 top-full z-[100] mt-2 w-80 rounded-lg border bg-white text-gray-900 shadow-xl">
      <div className="flex items-center justify-between border-b px-3 py-2">
        <span className="text-sm font-semibold">通知</span>
        <button
          type="button"
          onClick={markAllRead}
          disabled={unreadCount === 0}
          className="text-xs text-blue-600 hover:underline disabled:cursor-not-allowed disabled:text-gray-400"
        >
          全部標為已讀
        </button>
      </div>
      <div className="max-h-96 overflow-y-auto">
        {notifications.length === 0 ? (
          <div className="px-3 py-8 text-center text-sm text-gray-500">
            目前沒有通知
          </div>
        ) : (
          notifications
            .slice(0, 10)
            .map((item) => (
              <NotificationRow
                key={item.event_id}
                item={item}
                onClick={() => handleSelect(item)}
              />
            ))
        )}
      </div>
    </div>
  );
}

export default NotificationPanel;
