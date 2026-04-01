import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

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
        {isUser ? (
          <p className="text-sm whitespace-pre-wrap leading-relaxed">{content}</p>
        ) : (
          <div className="prose prose-sm prose-invert max-w-none [&_pre]:bg-gray-900 [&_pre]:rounded [&_pre]:p-2 [&_code]:text-xs [&_p]:my-1 [&_ul]:my-1 [&_ol]:my-1 [&_li]:my-0.5 [&_h1]:text-base [&_h2]:text-sm [&_h3]:text-sm [&_a]:text-blue-400">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
          </div>
        )}
        <span className={`text-xs mt-1 block ${isUser ? 'text-blue-200' : 'text-gray-500'}`}>
          {timestamp.toLocaleTimeString()}
        </span>
      </div>
    </div>
  );
}
