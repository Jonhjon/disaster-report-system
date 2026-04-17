import type { ChatMessage, EventCandidate, EventMapItem } from "../types";

const BASE_URL = "/api";

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
  const response = await fetch(`${BASE_URL}/events/map?${searchParams}`, {
    headers: { "Content-Type": "application/json" },
  });
  if (!response.ok) {
    throw new Error(`API Error: ${response.status} ${response.statusText}`);
  }
  return response.json();
}

export function streamChat(
  message: string,
  history: ChatMessage[],
  onText: (text: string) => void,
  onReportSubmitted: (data: Record<string, unknown>) => void,
  onDone: () => void,
  onError: (error: string) => void,
  onCandidatesSelection?: (candidates: EventCandidate[]) => void
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
              } else if (data.type === "candidates_selection") {
                onCandidatesSelection?.(data.candidates as EventCandidate[]);
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
