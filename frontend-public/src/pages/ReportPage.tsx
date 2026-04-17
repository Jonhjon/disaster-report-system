import ChatWindow from "../components/chat/ChatWindow";

function ReportPage() {
  return (
    <div className="mx-auto h-full max-w-3xl">
      <h1 className="mb-4 text-xl font-bold">通報災情</h1>
      <div className="h-[calc(100%-3rem)]">
        <ChatWindow />
      </div>
    </div>
  );
}

export default ReportPage;
