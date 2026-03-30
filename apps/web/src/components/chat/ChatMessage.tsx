interface Props {
  role: 'user' | 'assistant' | 'tool';
  content: string;
  timestamp: Date;
}

export function ChatMessage({ role, content, timestamp }: Props) {
  if (role === 'tool') {
    return (
      <div className="flex justify-center my-1">
        <span className="text-xs text-gray-500 bg-gray-800 px-3 py-1 rounded-full">
          {content}
        </span>
      </div>
    );
  }

  const isUser = role === 'user';

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-3`}>
      <div
        className={`max-w-[80%] rounded-lg px-4 py-2.5 ${
          isUser
            ? 'bg-blue-600 text-white'
            : 'bg-gray-800 text-gray-200 border border-gray-700'
        }`}
      >
        <p className="text-sm whitespace-pre-wrap leading-relaxed">{content}</p>
        <span className={`text-xs mt-1 block ${isUser ? 'text-blue-200' : 'text-gray-500'}`}>
          {timestamp.toLocaleTimeString()}
        </span>
      </div>
    </div>
  );
}
