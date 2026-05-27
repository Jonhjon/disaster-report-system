import type { ChatMessage } from "../types";

const ROLE_MARKER = /^\[(user|assistant)\][ \t]?/gm;

export function parseRawMessage(raw: string): ChatMessage[] {
  if (!raw) return [];

  type Marker = { role: ChatMessage["role"]; start: number; end: number };
  const markers: Marker[] = [];

  ROLE_MARKER.lastIndex = 0;
  let match: RegExpExecArray | null;
  while ((match = ROLE_MARKER.exec(raw)) !== null) {
    markers.push({
      role: match[1] as ChatMessage["role"],
      start: match.index,
      end: match.index + match[0].length,
    });
  }

  if (markers.length === 0) return [];

  const messages: ChatMessage[] = [];
  for (let i = 0; i < markers.length; i++) {
    const contentStart = markers[i].end;
    const contentEnd = i + 1 < markers.length ? markers[i + 1].start : raw.length;
    const content = raw.slice(contentStart, contentEnd).trim();
    if (content) {
      messages.push({ role: markers[i].role, content });
    }
  }

  return messages;
}
