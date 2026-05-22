// 對話送出與 SSE 接收 hook
import { useCallback, useEffect, useRef, useState } from 'react';
import { streamChat, type ChatStreamHandle } from '../api/chatClient';
import type { AttachmentOut, ChatMessage, EventCandidate } from '../types';

interface UseSSEChat {
  messages: ChatMessage[];
  isLoading: boolean;
  pendingCandidates: EventCandidate[] | null;
  reportResult: Record<string, unknown> | null;
  attachments: AttachmentOut[];
  addAttachment: (a: AttachmentOut) => void;
  removeAttachment: (id: string) => void;
  sendMessage: (text: string) => void;
  selectCandidate: (eventId: string) => void;
  reset: () => void;
}

export function useSSEChat(): UseSSEChat {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [pendingCandidates, setPendingCandidates] = useState<EventCandidate[] | null>(null);
  const [reportResult, setReportResult] = useState<Record<string, unknown> | null>(null);
  const [attachments, setAttachments] = useState<AttachmentOut[]>([]);
  const handleRef = useRef<ChatStreamHandle | null>(null);

  useEffect(() => () => handleRef.current?.close(), []);

  const sendMessage = useCallback(
    (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || isLoading) return;

      const attachmentIds = attachments.map((a) => a.id);
      setMessages((prev) => [...prev, { role: 'user', content: trimmed }]);
      setPendingCandidates(null);
      setIsLoading(true);

      let assistantContent = '';
      const historySnapshot = messages;

      handleRef.current = streamChat(trimmed, historySnapshot, attachmentIds, {
        onText: (delta) => {
          assistantContent += delta;
          setMessages((prev) => {
            const updated = [...prev];
            const last = updated[updated.length - 1];
            if (last?.role === 'assistant') {
              updated[updated.length - 1] = { ...last, content: assistantContent };
            } else {
              updated.push({ role: 'assistant', content: assistantContent });
            }
            return updated;
          });
        },
        onCandidatesSelection: (candidates) => setPendingCandidates(candidates),
        onReportSubmitted: (data) => {
          setReportResult(data);
          setPendingCandidates(null);
          setAttachments([]);
        },
        onError: (msg) => {
          setIsLoading(false);
          setPendingCandidates(null);
          setMessages((prev) => [...prev, { role: 'assistant', content: `發生錯誤：${msg}` }]);
        },
        onDone: () => setIsLoading(false),
      });
    },
    [attachments, isLoading, messages],
  );

  const selectCandidate = useCallback(
    (eventId: string) => {
      const text =
        eventId === 'new' ? '我選擇建立新事件' : `我選擇合併至事件 ${eventId}`;
      setPendingCandidates(null);
      sendMessage(text);
    },
    [sendMessage],
  );

  const addAttachment = useCallback(
    (a: AttachmentOut) => setAttachments((prev) => [...prev, a]),
    [],
  );
  const removeAttachment = useCallback(
    (id: string) => setAttachments((prev) => prev.filter((a) => a.id !== id)),
    [],
  );

  const reset = useCallback(() => {
    handleRef.current?.close();
    setMessages([]);
    setPendingCandidates(null);
    setReportResult(null);
    setAttachments([]);
    setIsLoading(false);
  }, []);

  return {
    messages,
    isLoading,
    pendingCandidates,
    reportResult,
    attachments,
    addAttachment,
    removeAttachment,
    sendMessage,
    selectCandidate,
    reset,
  };
}
