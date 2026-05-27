import type { ChatMessage } from "../../types";

interface ChatMessageViewProps {
  message: ChatMessage;
}

function ChatMessageView({ message }: ChatMessageViewProps) {
  const isUser = message.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[80%] rounded-lg px-4 py-2 text-sm ${
          isUser ? "bg-red-600 text-white" : "bg-gray-100 text-gray-800"
        }`}
      >
        <p className="whitespace-pre-wrap">{message.content}</p>
      </div>
    </div>
  );
}

export default ChatMessageView;
