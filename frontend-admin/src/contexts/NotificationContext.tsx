import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { playNotificationSound } from "../utils/notificationSound";
import { useAuth } from "./AuthContext";

export interface NotificationItem {
  event_id: string;
  title: string;
  disaster_type: string;
  severity: number;
  location_text: string;
  occurred_at: string;
  received_at: string;
  read: boolean;
}

interface NotificationContextValue {
  notifications: NotificationItem[];
  unreadCount: number;
  markAllRead: () => void;
  markRead: (eventId: string) => void;
}

const MAX_NOTIFICATIONS = 50;
const RECONNECT_BASE_MS = 1000;
const RECONNECT_MAX_MS = 30000;

const NotificationContext = createContext<NotificationContextValue>({
  notifications: [],
  unreadCount: 0,
  markAllRead: () => {},
  markRead: () => {},
});

interface RawPayload {
  event_id?: unknown;
  title?: unknown;
  disaster_type?: unknown;
  severity?: unknown;
  location_text?: unknown;
  occurred_at?: unknown;
}

export function parseNotification(raw: string): NotificationItem | null {
  try {
    const data = JSON.parse(raw) as RawPayload;
    if (
      typeof data.event_id !== "string" ||
      typeof data.title !== "string" ||
      typeof data.disaster_type !== "string" ||
      typeof data.severity !== "number" ||
      typeof data.location_text !== "string" ||
      typeof data.occurred_at !== "string"
    ) {
      return null;
    }
    return {
      event_id: data.event_id,
      title: data.title,
      disaster_type: data.disaster_type,
      severity: data.severity,
      location_text: data.location_text,
      occurred_at: data.occurred_at,
      received_at: new Date().toISOString(),
      read: false,
    };
  } catch {
    return null;
  }
}

export function NotificationProvider({ children }: { children: ReactNode }) {
  const { isAuthenticated } = useAuth();
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const sourceRef = useRef<EventSource | null>(null);
  const reconnectTimerRef = useRef<number | null>(null);
  const reconnectAttemptsRef = useRef(0);

  const closeStream = useCallback(() => {
    if (reconnectTimerRef.current !== null) {
      window.clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
    if (sourceRef.current) {
      sourceRef.current.close();
      sourceRef.current = null;
    }
  }, []);

  const handleNewEvent = useCallback((event: MessageEvent) => {
    const item = parseNotification(event.data);
    if (!item) return;
    setNotifications((prev) => {
      // 同 event_id 已存在 → 跳過（避免重連時重複）
      if (prev.some((n) => n.event_id === item.event_id)) return prev;
      const next = [item, ...prev];
      return next.length > MAX_NOTIFICATIONS
        ? next.slice(0, MAX_NOTIFICATIONS)
        : next;
    });
    playNotificationSound();
  }, []);

  const connect = useCallback(() => {
    const token = localStorage.getItem("token");
    if (!token) return;

    closeStream();
    const url = `/api/admin/notifications/stream?token=${encodeURIComponent(token)}`;
    const source = new EventSource(url);
    sourceRef.current = source;

    source.addEventListener("ready", () => {
      reconnectAttemptsRef.current = 0;
    });
    source.addEventListener("new_event", handleNewEvent as EventListener);
    source.onerror = () => {
      // EventSource 會自動嘗試重連，但若是 401 等永久錯誤就會持續失敗。
      // 我們關掉並改用退避重連，避免無限快速重試。
      source.close();
      sourceRef.current = null;
      const attempt = reconnectAttemptsRef.current + 1;
      reconnectAttemptsRef.current = attempt;
      const delay = Math.min(
        RECONNECT_BASE_MS * Math.pow(2, attempt - 1),
        RECONNECT_MAX_MS,
      );
      reconnectTimerRef.current = window.setTimeout(connect, delay);
    };
  }, [closeStream, handleNewEvent]);

  useEffect(() => {
    if (!isAuthenticated) {
      closeStream();
      reconnectAttemptsRef.current = 0;
      return;
    }
    connect();
    return closeStream;
  }, [isAuthenticated, connect, closeStream]);

  const markAllRead = useCallback(() => {
    setNotifications((prev) =>
      prev.every((n) => n.read) ? prev : prev.map((n) => ({ ...n, read: true })),
    );
  }, []);

  const markRead = useCallback((eventId: string) => {
    setNotifications((prev) =>
      prev.map((n) => (n.event_id === eventId ? { ...n, read: true } : n)),
    );
  }, []);

  const unreadCount = useMemo(
    () => notifications.filter((n) => !n.read).length,
    [notifications],
  );

  const value = useMemo<NotificationContextValue>(
    () => ({ notifications, unreadCount, markAllRead, markRead }),
    [notifications, unreadCount, markAllRead, markRead],
  );

  return (
    <NotificationContext.Provider value={value}>
      {children}
    </NotificationContext.Provider>
  );
}

export function useNotifications() {
  return useContext(NotificationContext);
}
