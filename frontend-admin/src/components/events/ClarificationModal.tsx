import { useEffect, useState } from "react";
import type {
  ClarificationChannel,
  Completeness,
  DisasterReport,
} from "../../types";
import {
  CLARIFICATION_CHANNEL_LABELS,
  MISSING_FIELD_LABELS,
} from "../../types";

interface ClarificationModalProps {
  open: boolean;
  onClose: () => void;
  onSubmit: (data: {
    question: string;
    channel: ClarificationChannel;
    recipient?: string;
  }) => Promise<void>;
  latestReport?: DisasterReport | null;
  completeness?: Completeness;
}

const CHANNEL_OPTIONS: ClarificationChannel[] = ["sms", "line", "email"];

function defaultQuestionFromMissing(missing: string[]): string {
  if (!missing.length) {
    return "";
  }
  const labels = missing.map((f) => MISSING_FIELD_LABELS[f] ?? f);
  return `您好，為了更準確掌握災情，請協助補充以下資訊：${labels.join("、")}。感謝您的配合。`;
}

function defaultRecipient(
  channel: ClarificationChannel,
  report?: DisasterReport | null
): string {
  if (!report) return "";
  if (channel === "sms") return report.reporter_phone ?? "";
  if (channel === "email") return report.reporter_email ?? "";
  if (channel === "line") return report.reporter_line_user_id ?? "";
  return "";
}

function ClarificationModal({
  open,
  onClose,
  onSubmit,
  latestReport,
  completeness,
}: ClarificationModalProps) {
  const initialChannel: ClarificationChannel =
    latestReport?.preferred_channel ?? "sms";
  const [channel, setChannel] = useState<ClarificationChannel>(initialChannel);
  const [recipient, setRecipient] = useState<string>(
    defaultRecipient(initialChannel, latestReport)
  );
  const [question, setQuestion] = useState<string>(
    defaultQuestionFromMissing(completeness?.missing ?? [])
  );
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    const ch = latestReport?.preferred_channel ?? "sms";
    setChannel(ch);
    setRecipient(defaultRecipient(ch, latestReport));
    setQuestion(defaultQuestionFromMissing(completeness?.missing ?? []));
    setError(null);
  }, [open, latestReport, completeness]);

  if (!open) return null;

  const handleChannelChange = (next: ClarificationChannel) => {
    setChannel(next);
    setRecipient(defaultRecipient(next, latestReport));
  };

  const handleSubmit = async () => {
    if (!question.trim()) {
      setError("請輸入追問問題");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await onSubmit({
        question: question.trim(),
        channel,
        recipient: recipient.trim() || undefined,
      });
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "送出失敗");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      role="dialog"
      aria-modal="true"
    >
      <div className="w-full max-w-lg rounded-lg bg-white p-6 shadow-xl">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-bold">📨 發送追問給民眾</h3>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600"
            aria-label="關閉"
          >
            ✕
          </button>
        </div>

        <div className="space-y-4 text-sm">
          <div>
            <label className="mb-1 block font-semibold text-gray-700">
              聯絡管道
            </label>
            <div className="flex gap-2">
              {CHANNEL_OPTIONS.map((c) => (
                <button
                  key={c}
                  type="button"
                  onClick={() => handleChannelChange(c)}
                  className={`rounded-lg border px-3 py-1 text-sm ${
                    channel === c
                      ? "border-red-500 bg-red-50 text-red-700"
                      : "border-gray-300 hover:bg-gray-50"
                  }`}
                >
                  {CLARIFICATION_CHANNEL_LABELS[c]}
                </button>
              ))}
            </div>
            {latestReport?.preferred_channel && (
              <p className="mt-1 text-xs text-gray-500">
                民眾偏好：
                {CLARIFICATION_CHANNEL_LABELS[latestReport.preferred_channel]}
              </p>
            )}
          </div>

          <div>
            <label className="mb-1 block font-semibold text-gray-700">
              收件人
            </label>
            <input
              type="text"
              value={recipient}
              onChange={(e) => setRecipient(e.target.value)}
              placeholder={
                channel === "sms"
                  ? "例：0912345678"
                  : channel === "email"
                    ? "例：user@example.com"
                    : "例：LINE user id"
              }
              className="w-full rounded-lg border px-3 py-2 focus:border-red-500 focus:outline-none"
            />
            <p className="mt-1 text-xs text-gray-500">
              留空會自動使用通報者登錄的聯絡資訊。
            </p>
          </div>

          <div>
            <label className="mb-1 block font-semibold text-gray-700">
              追問問題
            </label>
            <textarea
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              rows={4}
              maxLength={500}
              className="w-full resize-none rounded-lg border px-3 py-2 focus:border-red-500 focus:outline-none"
              placeholder="請輸入您想詢問民眾的問題..."
            />
            <p className="mt-1 text-right text-xs text-gray-500">
              {question.length}/500
            </p>
          </div>

          {error && (
            <p className="rounded bg-red-50 px-3 py-2 text-red-700">{error}</p>
          )}
        </div>

        <div className="mt-6 flex justify-end gap-2">
          <button
            onClick={onClose}
            disabled={submitting}
            className="rounded-lg border px-4 py-2 text-sm hover:bg-gray-50 disabled:opacity-50"
          >
            取消
          </button>
          <button
            onClick={handleSubmit}
            disabled={submitting || !question.trim()}
            className="rounded-lg bg-red-600 px-4 py-2 text-sm font-semibold text-white hover:bg-red-700 disabled:opacity-50"
          >
            {submitting ? "送出中..." : "送出追問"}
          </button>
        </div>
      </div>
    </div>
  );
}

export default ClarificationModal;
