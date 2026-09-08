import { type ZodType } from "zod";
import type {
  DisasterEvent,
  DisasterReport,
  EventListResponse,
  EventMapItem,
  EventStatistics,
  EventUpdateData,
  StatisticsQuery,
} from "../types";
import {
  DisasterEventSchema,
  EventListResponseSchema,
  EventStatisticsSchema,
} from "../schemas";
import { dateInTimeZone } from "../utils/format";

const BASE_URL = "/api";

function parseWith<T>(schema: ZodType<T>, raw: unknown): T {
  const result = schema.safeParse(raw);
  if (!result.success) {
    console.error("[API] Schema validation failed:", result.error.format());
    throw new Error(
      "API response 格式異常，請重新整理頁面或聯絡系統管理員。"
    );
  }
  return result.data;
}

async function fetchJSON<T>(url: string, options?: RequestInit): Promise<T> {
  const token = localStorage.getItem("token");
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(`${BASE_URL}${url}`, {
    headers,
    ...options,
  });

  if (response.status === 401) {
    localStorage.removeItem("token");
    window.location.href = "/login";
    throw new Error("認證已過期，請重新登入");
  }
  if (!response.ok) {
    let detail: unknown;
    try {
      detail = (await response.json())?.detail;
    } catch {
      // Non-JSON errors fall back to the HTTP status below.
    }
    throw new Error(
      typeof detail === "string"
        ? detail
        : `API Error: ${response.status} ${response.statusText}`
    );
  }
  return response.json();
}

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
  const raw = await fetchJSON<unknown>(`/events?${searchParams}`);
  return parseWith(EventListResponseSchema, raw);
}

export async function getEvent(id: string): Promise<DisasterEvent> {
  const raw = await fetchJSON<unknown>(`/events/${id}`);
  return parseWith(DisasterEventSchema, raw);
}

export async function updateEvent(
  id: string,
  data: EventUpdateData
): Promise<DisasterEvent> {
  const raw = await fetchJSON<unknown>(`/events/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
  return parseWith(DisasterEventSchema, raw);
}

export async function deleteEvent(id: string): Promise<void> {
  const token = localStorage.getItem("token");
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  const response = await fetch(`${BASE_URL}/events/${id}`, {
    method: "DELETE",
    headers,
  });
  if (response.status === 401) {
    localStorage.removeItem("token");
    window.location.href = "/login";
    throw new Error("認證已過期，請重新登入");
  }
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
  locationText: string
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

export async function mergeEvents(
  targetEventId: string,
  sourceEventId: string
): Promise<DisasterEvent> {
  const raw = await fetchJSON<unknown>(
    `/events/${targetEventId}/merge-from/${sourceEventId}`,
    { method: "POST" }
  );
  return parseWith(DisasterEventSchema, raw);
}

export async function getLLMLogs(): Promise<Record<string, unknown>[]> {
  return fetchJSON("/llm-logs");
}

function toQueryString(params: object): string {
  const searchParams = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== "") {
      searchParams.set(key, String(value));
    }
  });
  return searchParams.toString();
}

export async function getEventStatistics(
  params: StatisticsQuery,
  signal?: AbortSignal
): Promise<EventStatistics> {
  const raw = await fetchJSON<unknown>(
    `/events/statistics?${toQueryString(params)}`,
    { signal }
  );
  return parseWith(EventStatisticsSchema, raw);
}

/**
 * 下載事件明細 CSV。
 *
 * 不能用 <a download href> 或 window.open：那樣不會帶 Authorization header，
 * 後端回 401 之後 fetchJSON 的 401 分支會清掉 token 並導向 /login
 * ——使用者按下匯出的結果會是「被登出」。必須自己 fetch 後轉成 blob。
 */
export async function downloadEventsCsv(
  params: Omit<StatisticsQuery, "bucket"> & { sort_by?: string; sort_order?: string }
): Promise<{ blob: Blob; filename: string; truncated: boolean }> {
  const token = localStorage.getItem("token");
  const headers: Record<string, string> = {};
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(
    `${BASE_URL}/events/export.csv?${toQueryString(params)}`,
    { headers }
  );

  if (response.status === 401) {
    localStorage.removeItem("token");
    window.location.href = "/login";
    throw new Error("認證已過期，請重新登入");
  }
  if (!response.ok) {
    throw new Error(`API Error: ${response.status} ${response.statusText}`);
  }

  const stamp = dateInTimeZone(new Date(), "Asia/Taipei");
  return {
    blob: await response.blob(),
    filename: `災情事件明細_${stamp}.csv`,
    truncated: response.headers.get("X-Truncated") === "true",
  };
}
