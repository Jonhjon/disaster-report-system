import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import ChatWindow from "../components/chat/ChatWindow";
import { getChatSession } from "../services/api";
import type { ChatMessage, PendingQuestion } from "../types";

function ResumeReportPage() {
  const { token } = useParams<{ token: string }>();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [pendingQuestions, setPendingQuestions] = useState<PendingQuestion[]>([]);

  useEffect(() => {
    if (!token) {
      setError("連結無效");
      setLoading(false);
      return;
    }
    let cancelled = false;

    (async () => {
      try {
        const session = await getChatSession(token);
        if (cancelled) return;
        const baseMessages: ChatMessage[] = [...session.messages];
        // 將 pending_questions 轉成 assistant 訊息置於最後
        const pendingAsAssistant = session.pending_questions.map((q) => ({
          role: "assistant" as const,
          content: `【通報中心追問】${q.question}`,
        }));
        setMessages([...baseMessages, ...pendingAsAssistant]);
        setPendingQuestions(session.pending_questions);
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "載入失敗");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [token]);

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center text-gray-500">
        載入對話中...
      </div>
    );
  }

  if (error) {
    return (
      <div className="mx-auto max-w-xl p-6 text-center">
        <p className="mb-2 text-lg font-semibold text-red-600">
          無法載入對話
        </p>
        <p className="text-sm text-gray-600">{error}</p>
        <p className="mt-4 text-sm">
          連結可能已過期，請透過新對話重新通報災情。
        </p>
      </div>
    );
  }

  const introText =
    pendingQuestions.length > 0
      ? `通報中心正在等您回覆 ${pendingQuestions.length} 則追問，請依據提示補充資訊。`
      : "您已回到原本的通報對話，可以繼續補充資訊。";

  return (
    <div className="mx-auto h-full max-w-3xl">
      <h1 className="mb-4 text-xl font-bold">續接通報 · 補充資訊</h1>
      <div className="h-[calc(100%-3rem)]">
        <ChatWindow
          initialMessages={messages}
          sessionToken={token}
          introText={introText}
        />
      </div>
    </div>
  );
}

export default ResumeReportPage;
