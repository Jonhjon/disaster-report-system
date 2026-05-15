import { useState, useRef, useEffect } from "react";
import { AlertTriangle, MessageSquare } from "lucide-react";
import ChatMessage from "./ChatMessage";
import ReportSummary from "./ReportSummary";
import CandidateSelectionCard from "./CandidateSelectionCard";
import PhotoUploader from "./PhotoUploader";
import { streamChat } from "../../services/api";
import type {
  AttachmentOut,
  ChatMessage as ChatMessageType,
  EventCandidate,
} from "../../types";

interface ChatWindowProps {
  introText?: string;
}

function ChatWindow({ introText }: ChatWindowProps = {}) {
  const [messages, setMessages] = useState<ChatMessageType[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [reportResult, setReportResult] = useState<Record<
    string,
    unknown
  > | null>(null);
  const [pendingCandidates, setPendingCandidates] = useState<EventCandidate[] | null>(null);
  const [attachments, setAttachments] = useState<AttachmentOut[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const controllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, pendingCandidates]);

  // M-6：unmount 時中止進行中的 SSE 串流，避免在已卸載元件上呼叫 setState 造成記憶體洩漏。
  useEffect(() => {
    return () => {
      controllerRef.current?.abort();
    };
  }, []);

  const sendMessage = (userMessage: string) => {
    if (!userMessage.trim() || isLoading) return;

    const attachmentIds = attachments.map((a) => a.id);

    setInput("");
    setPendingCandidates(null);
    setMessages((prev) => [...prev, { role: "user", content: userMessage }]);
    setIsLoading(true);

    let assistantContent = "";

    controllerRef.current = streamChat(
      userMessage,
      messages,
      attachmentIds,
      (text) => {
        assistantContent += text;
        setMessages((prev) => {
          const updated = [...prev];
          const lastMsg = updated[updated.length - 1];
          if (lastMsg?.role === "assistant") {
            updated[updated.length - 1] = {
              ...lastMsg,
              content: assistantContent,
            };
          } else {
            updated.push({ role: "assistant", content: assistantContent });
          }
          return updated;
        });
      },
      (data) => {
        setReportResult(data);
        setPendingCandidates(null);
        setAttachments([]);
      },
      () => {
        setIsLoading(false);
      },
      (error) => {
        setIsLoading(false);
        setPendingCandidates(null);
        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: `發生錯誤：${error}` },
        ]);
      },
      (candidates) => {
        setPendingCandidates(candidates);
      }
    );
  };

  const handleSend = () => {
    sendMessage(input.trim());
  };

  const handleCandidateSelect = (eventId: string) => {
    const choiceText =
      eventId === "new"
        ? "我選擇建立新事件"
        : `我選擇合併至事件 ${eventId}`;
    setPendingCandidates(null);
    sendMessage(choiceText);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex h-full flex-col rounded-lg border bg-white">
      <div className="flex-1 overflow-auto p-4">
        {messages.length === 0 && !pendingCandidates && (
          <div className="flex h-full items-center justify-center text-gray-400">
            <div className="text-center">
              <AlertTriangle size={48} className="mx-auto mb-2" aria-hidden="true" />
              <p className="text-lg font-semibold">智慧災害通報助手</p>
              <p className="text-sm">請描述您要通報的災情，AI 助手會引導您完成通報</p>
            </div>
          </div>
        )}
        {introText && messages.length > 0 && (
          <div className="mx-2 mb-3 flex items-start gap-2 rounded-lg border border-yellow-300 bg-yellow-50 p-3 text-sm text-yellow-900">
            <MessageSquare size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
            {introText}
          </div>
        )}
        {messages.map((msg, i) => (
          <ChatMessage key={i} message={msg} />
        ))}
        {pendingCandidates && (
          <CandidateSelectionCard
            candidates={pendingCandidates}
            onSelect={handleCandidateSelect}
          />
        )}
        {reportResult && <ReportSummary result={reportResult} />}
        <div ref={messagesEndRef} />
      </div>

      <div className="border-t p-3">
        <PhotoUploader
          attachments={attachments}
          onAdd={(a) => setAttachments((prev) => [...prev, a])}
          onRemove={(id) =>
            setAttachments((prev) => prev.filter((a) => a.id !== id))
          }
          disabled={isLoading}
        />
        <div className="flex gap-2">
          <textarea
            className="flex-1 resize-none rounded-lg border px-3 py-2 text-sm focus:border-red-500 focus:outline-none"
            rows={2}
            placeholder="請描述災情狀況..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isLoading}
          />
          <button
            onClick={handleSend}
            disabled={isLoading || !input.trim()}
            className="rounded-lg bg-red-600 px-4 py-2 text-sm font-semibold text-white hover:bg-red-700 disabled:opacity-50"
          >
            {isLoading ? "處理中..." : "送出"}
          </button>
        </div>
      </div>
    </div>
  );
}

export default ChatWindow;
