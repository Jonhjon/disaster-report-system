import { z } from "zod";

const DisasterTypeSchema = z.enum([
  "trapped",
  "road_collapse",
  "flooding",
  "landslide",
  "small_landslide",
  "building_damage",
  "utility_damage",
  "fire",
  "other",
]);

const EventStatusSchema = z.enum([
  "reported",
  "in_progress",
  "resolved",
]);

export const DisasterEventSchema = z.object({
  id: z.string(),
  title: z.string(),
  disaster_type: DisasterTypeSchema,
  severity: z.number(),
  description: z.string().nullable(),
  location_text: z.string(),
  latitude: z.number(),
  longitude: z.number(),
  occurred_at: z.string(),
  casualties: z.number(),
  injured: z.number(),
  trapped: z.number(),
  status: EventStatusSchema,
  report_count: z.number(),
  location_approximate: z.boolean(),
  occurred_at_approximate: z.boolean(),
  created_at: z.string(),
  updated_at: z.string(),
});

export const EventMapItemSchema = z.object({
  id: z.string(),
  title: z.string(),
  disaster_type: DisasterTypeSchema,
  severity: z.number(),
  latitude: z.number(),
  longitude: z.number(),
  status: EventStatusSchema,
  report_count: z.number(),
  occurred_at: z.string(),
  location_approximate: z.boolean(),
  occurred_at_approximate: z.boolean(),
});

export const EventListResponseSchema = z.object({
  items: z.array(DisasterEventSchema),
  total: z.number(),
  page: z.number(),
  page_size: z.number(),
  total_pages: z.number(),
});
