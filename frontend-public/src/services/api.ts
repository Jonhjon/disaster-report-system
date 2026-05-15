import { z, type ZodType } from "zod";
import type {
  AttachmentOut,
  ChatMessage,
  EventCandidate,
  EventMapItem,
} from "../types";
import { EventMapItemSchema } from "../schemas/event";

const BASE_URL = "/api";

export const ALLOWED_PHOTO_TYPES = [
  "image/jpeg",
  "image/png",
  "image/webp",
] as const;
export const MAX_PHOTO_BYTES = 5 * 1024 * 1024;
export const MAX_PHOTOS_PER_REPORT = 3;

function parseWith<T>(schema: ZodType<T>, raw: unknown): T {
  const result = schema.safeParse(raw);
  if (!result.success) {
    console.error("[API] Schema validation failed:", result.error.format());
    throw new Error("API response 格式異常，請重新整理頁面。");
  }
  return result.data;
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
  const response = await fetch(`${BASE_URL}/events/map?${searchParams}`, {
    headers: { "Content-Type": "application/json" },
  });
  if (!response.ok) {
    throw new Error(`API Error: ${response.status} ${response.statusText}`);
  }
  const raw: unknown = await response.json();
  return parseWith(z.object({ items: z.array(EventMapItemSchema) }), raw);
}

export async function uploadPhoto(file: File): Promise<AttachmentOut> {
  if (!ALLOWED_PHOTO_TYPES.includes(file.type as (typeof ALLOWED_PHOTO_TYPES)[number])) {
    throw new Error(`僅支援 JPEG / PNG / WebP（收到 ${file.type || "未知格式"}）`);
  }
  if (file.size > MAX_PHOTO_BYTES) {
    throw new Error(
      `檔案大小超過 ${Math.round(MAX_PHOTO_BYTES / 1024 / 1024)} MB 上限`,
    );
  }

  const form = new FormData();
  form.append("file", file);

  const response = await fetch(`${BASE_URL}/uploads/photo`, {
    method: "POST",
    body: form,
  });
  if (!response.ok) {
    let detail = `上傳失敗（${response.status}）`;
    try {
      const body = await response.json();
      if (body?.detail) detail = String(body.detail);
    } catch {
      // ignore
    }
    throw new Error(detail);
  }
  return response.json();
}

export function streamChat(
  message: string,
  history: ChatMessage[],
  attachmentIds: string[],
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
    body: JSON.stringify({ message, history, attachment_ids: attachmentIds }),
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
