import ReactMarkdown from 'react-markdown';
import rehypeSanitize from 'rehype-sanitize';
import { cn } from '@/lib/utils';

interface Props {
  role: 'user' | 'assistant' | 'tool';
  content: string;
  timestamp: Date;
}

export function ChatMessage({ role, content, timestamp }: Props) {
  if (role === 'tool') {
    return (
      <div className="flex justify-center my-1">
        <span className="text-xs text-[hsl(var(--neutral-400))] bg-[hsl(var(--neutral-800))] px-3 py-1 rounded-full border border-[hsl(var(--surface-glass-border))]">
          {content}
        </span>
      </div>
    );
  }

  const isUser = role === 'user';

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-3`}>
      <div
        className={cn(
          'max-w-[80%] rounded-xl px-4 py-2.5',
          isUser
            ? 'bg-[hsl(var(--brand-500))] text-white'
            : 'bg-[hsl(var(--surface-glass))] text-[hsl(var(--neutral-200))] border border-[hsl(var(--surface-glass-border))] backdrop-blur-sm',
        )}
      >
        {isUser ? (
          <p className="text-sm whitespace-pre-wrap leading-relaxed">{content}</p>
        ) : (
          <div className="prose prose-sm prose-invert max-w-none [&_pre]:bg-[hsl(var(--neutral-900))] [&_pre]:rounded-lg [&_pre]:p-2 [&_pre]:border [&_pre]:border-[hsl(var(--surface-glass-border))] [&_code]:text-xs [&_p]:my-1 [&_ul]:my-1 [&_ol]:my-1 [&_li]:my-0.5 [&_h1]:text-base [&_h2]:text-sm [&_h3]:text-sm [&_a]:text-[hsl(var(--brand-300))]">
            <ReactMarkdown rehypePlugins={[rehypeSanitize]}>{content}</ReactMarkdown>
          </div>
        )}
        <span className={cn(
          'text-xs mt-1 block',
          isUser ? 'text-white/70' : 'text-[hsl(var(--neutral-500))]',
        )}>
          {timestamp.toLocaleTimeString()}
        </span>
      </div>
    </div>
  );
}
