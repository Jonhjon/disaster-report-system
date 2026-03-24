import type {
  DisasterEvent,
  DisasterReport,
  EventListResponse,
  EventMapItem,
  EventUpdateData,
  ChatMessage,
} from "../types";

const BASE_URL = "/api";

async function fetchJSON<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}${url}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    throw new Error(`API Error: ${response.status} ${response.statusText}`);
  }
  return response.json();
}

// Events API
export async function getEvents(params: {
  search?: string;
  disaster_type?: string;
  severity_min?: number;
  severity_max?: number;
  status?: string;
  date_from?: string;
  date_to?: string;
  sort_by?: string;
  sort_order?: string;
  page?: number;
  page_size?: number;
}): Promise<EventListResponse> {
  const searchParams = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== "") {
      searchParams.set(key, String(value));
    }
  });
  return fetchJSON(`/events?${searchParams}`);
}

export async function getEvent(id: string): Promise<DisasterEvent> {
  return fetchJSON(`/events/${id}`);
}

export async function updateEvent(
  id: string,
  data: EventUpdateData
): Promise<DisasterEvent> {
  return fetchJSON(`/events/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function deleteEvent(id: string): Promise<void> {
  const response = await fetch(`${BASE_URL}/events/${id}`, {
    method: "DELETE",
    headers: { "Content-Type": "application/json" },
  });
  if (!response.ok) {
    throw new Error(`API Error: ${response.status} ${response.statusText}`);
  }
}

export async function getEventReports(
  eventId: string
): Promise<{ items: DisasterReport[]; total: number }> {
  return fetchJSON(`/events/${eventId}/reports`);
}

export async function updateEventLocation(
  id: string,
  locationText: string,
): Promise<EventMapItem> {
  return fetchJSON(`/events/${id}/location`, {
    method: "PATCH",
    body: JSON.stringify({ location_text: locationText }),
  });
}

export async function getMapEvents(params: {
  bounds?: string;
  disaster_type?: string;
  severity_min?: number;
  status?: string;
}): Promise<{ items: EventMapItem[] }> {
  const searchParams = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== "") {
      searchParams.set(key, String(value));
    }
  });
  return fetchJSON(`/events/map?${searchParams}`);
}

// Chat API (SSE streaming)
export function streamChat(
  message: string,
  history: ChatMessage[],
  onText: (text: string) => void,
  onReportSubmitted: (data: Record<string, unknown>) => void,
  onDone: () => void,
  onError: (error: string) => void
): AbortController {
  const controller = new AbortController();

  fetch(`${BASE_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, history }),
    signal: controller.signal,
  })
    .then(async (response) => {
      if (!response.ok) throw new Error("Chat API error");
      const reader = response.body?.getReader();
      if (!reader) throw new Error("No response body");

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            try {
              const data = JSON.parse(line.slice(6));
              if (data.type === "text") {
                onText(data.content);
              } else if (data.type === "report_submitted") {
                onReportSubmitted(data);
              } else if (data.type === "done") {
                onDone();
              } else if (data.type === "error") {
                onError(data.message || "發生未知錯誤");
                return;
              }
            } catch {
              // skip malformed data
            }
          }
        }
      }
      onDone();
    })
    .catch((err) => {
      if (err.name !== "AbortError") {
        const msg =
          err.message === "Failed to fetch"
            ? "無法連線至伺服器，請確認後端服務是否正常運作。"
            : err.message;
        onError(msg);
      }
    });

  return controller;
}
