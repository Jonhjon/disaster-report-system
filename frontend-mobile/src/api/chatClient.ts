// 對話 SSE 串流：對應後端 POST /api/chat（sse-starlette）
import EventSource from 'react-native-sse';
import { apiUrl } from '../config/env';
import { getSessionSnapshot } from '../stores/sessionStore';
import type { ChatMessage, EventCandidate } from '../types';

export interface ChatStreamCallbacks {
  onText: (text: string) => void;
  onReportSubmitted: (data: Record<string, unknown>) => void;
  onCandidatesSelection?: (candidates: EventCandidate[]) => void;
  onError: (msg: string) => void;
  onDone: () => void;
}

export interface ChatStreamHandle {
  close: () => void;
}

export function streamChat(
  message: string,
  history: ChatMessage[],
  attachmentIds: string[],
  callbacks: ChatStreamCallbacks,
): ChatStreamHandle {
  const { verifiedPhone, deviceLocation } = getSessionSnapshot();

  const body: Record<string, unknown> = {
    message,
    history,
    attachment_ids: attachmentIds,
  };
  if (verifiedPhone) body.verified_phone = verifiedPhone;
  if (deviceLocation) body.device_location = deviceLocation;

  const url = apiUrl('/chat');
  const es = new EventSource(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    pollingInterval: 0, // 不重連
  });

  let closed = false;
  const close = () => {
    if (closed) return;
    closed = true;
    es.close();
  };

  es.addEventListener('message', (event) => {
    if (closed) return;
    if (!event.data) return;
    try {
      const data = JSON.parse(event.data);
      if (data.type === 'text') callbacks.onText(data.content ?? '');
      else if (data.type === 'candidates_selection') {
        callbacks.onCandidatesSelection?.(data.candidates ?? []);
      } else if (data.type === 'report_submitted') {
        callbacks.onReportSubmitted(data);
      } else if (data.type === 'done') {
        callbacks.onDone();
        close();
      } else if (data.type === 'error') {
        callbacks.onError(data.message ?? '發生未知錯誤');
        close();
      }
    } catch {
      // skip malformed chunk
    }
  });

  es.addEventListener('error', (e: unknown) => {
    if (closed) return;
    const msg =
      e && typeof e === 'object' && 'message' in e
        ? String((e as { message?: unknown }).message)
        : '網路連線失敗';
    callbacks.onError(msg);
    close();
  });

  return { close };
}
