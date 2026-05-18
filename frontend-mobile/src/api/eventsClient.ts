// 災情事件 API：對應後端 /api/events/map
import axios from 'axios';
import { apiUrl } from '../config/env';
import type { EventMapItem } from '../types';

export interface MapEventsQuery {
  bounds?: string;
  disaster_type?: string;
  severity_min?: number;
  status?: string;
}

export async function getMapEvents(
  params: MapEventsQuery = {},
): Promise<EventMapItem[]> {
  const response = await axios.get<{ items: EventMapItem[] }>(apiUrl('/events/map'), {
    params,
    timeout: 15000,
  });
  return response.data.items ?? [];
}
