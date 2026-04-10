export interface DisasterEvent {
  id: string;
  title: string;
  disaster_type: DisasterType;
  severity: number;
  description: string | null;
  location_text: string;
  latitude: number;
  longitude: number;
  occurred_at: string;
  casualties: number;
  injured: number;
  trapped: number;
  status: EventStatus;
  report_count: number;
  location_approximate: boolean;
  created_at: string;
  updated_at: string;
}

export interface DisasterReport {
  id: string;
  event_id: string | null;
  reporter_name: string | null;
  reporter_phone: string | null;
  raw_message: string;
  extracted_data: Record<string, unknown>;
  location_text: string | null;
  geocoded_address: string | null;
  created_at: string;
}

export type DisasterType =
  | "trapped"
  | "road_collapse"
  | "flooding"
  | "landslide"
  | "small_landslide"
  | "building_damage"
  | "utility_damage"
  | "fire"
  | "other";

export type EventStatus = "reported" | "in_progress" | "resolved";

export interface EventListResponse {
  items: DisasterEvent[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface EventMapItem {
  id: string;
  title: string;
  disaster_type: DisasterType;
  severity: number;
  latitude: number;
  longitude: number;
  status: EventStatus;
  report_count: number;
  occurred_at: string;
  location_approximate: boolean;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface EventCandidate {
  event_id: string;
  title: string;
  description: string;
  location_text: string;
  report_count: number;
  distance_m: number;
  score: number;
}

export interface EventUpdateData {
  title?: string;
  severity?: number;
  description?: string;
  status?: EventStatus;
  casualties?: number;
  injured?: number;
  trapped?: number;
}

export const DISASTER_TYPE_LABELS: Record<DisasterType, string> = {
  trapped: "人員受困",
  road_collapse: "路段崩塌",
  flooding: "淹水",
  landslide: "土石流",
  small_landslide: "小型土石流",
  building_damage: "建物受損",
  utility_damage: "管線/電力受損",
  fire: "火警",
  other: "其他",
};

export const STATUS_LABELS: Record<EventStatus, string> = {
  reported: "通報中",
  in_progress: "處理中",
  resolved: "已結案",
};

export const SEVERITY_LABELS: Record<number, string> = {
  1: "輕微",
  2: "中等",
  3: "嚴重",
  4: "非常嚴重",
  5: "極嚴重",
};

export const DISASTER_TYPE_COLORS: Record<DisasterType, string> = {
  trapped: "#9b59b6",
  road_collapse: "#e67e22",
  flooding: "#2980b9",
  landslide: "#d35400",
  small_landslide: "#8B4513",
  building_damage: "#e74c3c",
  utility_damage: "#f39c12",
  fire: "#c0392b",
  other: "#95a5a6",
};
