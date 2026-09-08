import { z } from "zod";

// 分組 key 一律用 z.string() 而非 z.enum：資料庫對 disaster_type 沒有
// CheckConstraint，可能存在 LLM 枚舉清單以外的值（例如既有測試資料裡的
// "earthquake"）。若用 z.enum，一筆例外資料就會讓整個統計頁噴
// 「API response 格式異常」而完全打不開。標籤查表時再用 ?? key 兜底。
const CategoryCountSchema = z.object({
  key: z.string(),
  count: z.number(),
  percentage: z.number(),
});

const TrendPointSchema = z.object({
  bucket_start: z.string(),
  count: z.number(),
});

const CrossTabCellSchema = z.object({
  disaster_type: z.string(),
  severity: z.number(),
  count: z.number(),
});

const ResolutionStatsSchema = z.object({
  resolved_count: z.number(),
  legacy_excluded_count: z.number(),
  avg_hours: z.number().nullable(),
  median_hours: z.number().nullable(),
  p90_hours: z.number().nullable(),
  method_note: z.string(),
});

const StatisticsSummarySchema = z.object({
  total_events: z.number(),
  total_report_count: z.number(),
  total_casualties: z.number(),
  total_injured: z.number(),
  total_severe_injured: z.number(),
  total_trapped: z.number(),
  avg_severity: z.number().nullable(),
  high_severity_count: z.number(),
  unresolved_count: z.number(),
});

export const EventStatisticsSchema = z.object({
  summary: StatisticsSummarySchema,
  by_disaster_type: z.array(CategoryCountSchema),
  by_severity: z.array(CategoryCountSchema),
  by_status: z.array(CategoryCountSchema),
  trend: z.array(TrendPointSchema),
  cross_tab: z.array(CrossTabCellSchema),
  resolution: ResolutionStatsSchema,
  bucket: z.string(),
  timezone: z.string(),
  time_field: z.string(),
  generated_at: z.string(),
});
