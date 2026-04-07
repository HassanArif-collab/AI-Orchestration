import { useState, useRef, useEffect, useMemo } from 'react';
import { Send, Loader2, Trash2 } from 'lucide-react';
import { useChat } from '../../hooks/useChat';
import { ChatMessage } from './ChatMessage';
import { cn } from '@/lib/utils';

/**
 * Simple debounce hook for values that change rapidly
 * (e.g., activeTools list that adds/removes items in quick succession).
 */
function useDebouncedValue<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);

  return debounced;
}

export function ChatPanel() {
  const {
    messages,
    isLoading,
    activeTools,
    currentStage,
    streamingText,
    error,
    sendMessage,
    clearHistory,
  } = useChat();
  const [input, setInput] = useState('');
  const bottomRef = useRef<HTMLDivElement>(null);
  const [workingTime, setWorkingTime] = useState(0);

  // Debounce activeTools to prevent rapid add/remove flickering
  const debouncedTools = useDebouncedValue(activeTools, 200);

  // Auto-scroll on new messages or streaming updates
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages.length, streamingText]);

  // Track how long AI has been working
  useEffect(() => {
    if (!isLoading) {
      setWorkingTime(0);
      return;
    }

    const timer = setInterval(() => {
      setWorkingTime((prev) => prev + 1);
    }, 1000);

    return () => clearInterval(timer);
  }, [isLoading]);

  const handleSend = async () => {
    const text = input.trim();
    if (!text || isLoading) return;
    setInput('');
    await sendMessage(text);
  };

  /** Click a suggestion chip — auto-send immediately */
  const handleChipClick = (prompt: string) => {
    setInput(prompt);
    // Use setTimeout to ensure input state is committed before sending
    setTimeout(() => {
      if (!isLoading) {
        sendMessage(prompt);
      }
    }, 0);
  };

  const getButtonLabel = () => {
    if (!isLoading) return 'Send';

    if (currentStage === 'sending') return 'Sending...';
    if (currentStage === 'tools' && debouncedTools.length > 0) {
      return `Using: ${debouncedTools[0]}...`;
    }
    if (currentStage === 'streaming') return 'Generating...';
    if (currentStage === 'error') return 'Send';

    return 'Thinking...';
  };

  // Single unified status — replaces multiple scattered indicators
  const status = useMemo(() => {
    if (error) {
      return {
        icon: 'Warning' as const,
        text: error,
        className: 'text-red-300 border-red-500/30 bg-red-500/10',
      };
    }

    if (!isLoading) return null;

    if (debouncedTools.length > 0) {
      return {
        icon: 'Tool' as const,
        text: `Using tools: ${debouncedTools.join(', ')}`,
        className: 'text-blue-300 border-blue-500/30 bg-blue-500/10',
      };
    }

    if (currentStage === 'streaming' && streamingText) {
      return {
        icon: 'Writing' as const,
        text: `Writing response (${streamingText.length} chars)...`,
        className: 'text-emerald-300 border-emerald-500/30 bg-emerald-500/10',
      };
    }

    return {
      icon: 'Thinking' as const,
      text: 'Thinking...',
      className: 'text-[hsl(var(--neutral-400))] border-[hsl(var(--surface-glass-border))] bg-[hsl(var(--surface-glass))] animate-pulse',
    };
  }, [error, isLoading, debouncedTools, currentStage, streamingText]);

  const StatusIcon = ({ type }: { type: string }) => {
    switch (type) {
      case 'Warning':
        return <span className="w-2 h-2 rounded-full bg-red-400 shrink-0" />;
      case 'Tool':
        return <span className="w-2 h-2 rounded-full bg-blue-400 shrink-0 animate-pulse" />;
      case 'Writing':
        return <span className="w-2 h-2 rounded-full bg-emerald-400 shrink-0 animate-pulse" />;
      default:
        return <span className="w-2 h-2 rounded-full bg-[hsl(var(--neutral-400))] shrink-0 animate-pulse" />;
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between p-3 border-b border-[hsl(var(--surface-glass-border))] shrink-0 bg-[hsl(var(--surface-glass))] backdrop-blur-md">
        <div>
          <h3 className="text-sm font-semibold text-[hsl(var(--neutral-100))]">Chat Assistant</h3>
          <p className="text-xs text-[hsl(var(--neutral-500))]">Ask about your pipeline, research, or YouTube</p>
        </div>
        <button
          onClick={clearHistory}
          className="flex items-center gap-1 text-xs text-[hsl(var(--neutral-500))] hover:text-[hsl(var(--neutral-100))] px-2 py-1 rounded-lg bg-[hsl(var(--neutral-800))] hover:bg-[hsl(var(--neutral-700))] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[hsl(var(--brand-500))]"
        >
          <Trash2 className="w-3 h-3" strokeWidth={1.5} />
          Clear
        </button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-3">
        {messages.length === 0 && (
          <div className="text-center text-[hsl(var(--neutral-500))] text-sm mt-8">
            <p className="mb-4">Ask me anything about your content pipeline.</p>
            <div className="grid grid-cols-2 gap-2">
              <button
                onClick={() => handleChipClick('What cards are in the pipeline?')}
                className="text-left bg-[hsl(var(--surface-glass))] hover:bg-[hsl(var(--neutral-800))] border border-[hsl(var(--surface-glass-border))] rounded-xl p-3 transition-colors group"
              >
                <p className="text-[hsl(var(--neutral-100))] text-xs font-medium group-hover:text-[hsl(var(--brand-300))]">Pipeline Status</p>
                <p className="text-[hsl(var(--neutral-500))] text-[10px] mt-0.5">&quot;What cards are in the pipeline?&quot;</p>
              </button>
              <button
                onClick={() => handleChipClick('Show my published scripts')}
                className="text-left bg-[hsl(var(--surface-glass))] hover:bg-[hsl(var(--neutral-800))] border border-[hsl(var(--surface-glass-border))] rounded-xl p-3 transition-colors group"
              >
                <p className="text-[hsl(var(--neutral-100))] text-xs font-medium group-hover:text-[hsl(var(--brand-300))]">Published Scripts</p>
                <p className="text-[hsl(var(--neutral-500))] text-[10px] mt-0.5">&quot;Show my published scripts&quot;</p>
              </button>
              <button
                onClick={() => handleChipClick('Search for AI regulation news')}
                className="text-left bg-[hsl(var(--surface-glass))] hover:bg-[hsl(var(--neutral-800))] border border-[hsl(var(--surface-glass-border))] rounded-xl p-3 transition-colors group"
              >
                <p className="text-[hsl(var(--neutral-100))] text-xs font-medium group-hover:text-[hsl(var(--brand-300))]">Web Search</p>
                <p className="text-[hsl(var(--neutral-500))] text-[10px] mt-0.5">&quot;Search for AI regulation news&quot;</p>
              </button>
              <button
                onClick={() => handleChipClick('How are competitor channels doing?')}
                className="text-left bg-[hsl(var(--surface-glass))] hover:bg-[hsl(var(--neutral-800))] border border-[hsl(var(--surface-glass-border))] rounded-xl p-3 transition-colors group"
              >
                <p className="text-[hsl(var(--neutral-100))] text-xs font-medium group-hover:text-[hsl(var(--brand-300))]">YouTube Analytics</p>
                <p className="text-[hsl(var(--neutral-500))] text-[10px] mt-0.5">&quot;How are competitor channels doing?&quot;</p>
              </button>
            </div>
          </div>
        )}

        {messages.map((msg) => (
          <ChatMessage
            key={msg.id}
            role={msg.role}
            content={msg.content}
            timestamp={msg.timestamp}
          />
        ))}

        {/* Streaming message with typewriter cursor */}
        {isLoading && streamingText && (
          <div className="flex justify-start mb-2">
            <div className="max-w-[80%] rounded-xl p-3 bg-[hsl(var(--surface-glass))] text-[hsl(var(--neutral-100))] border border-[hsl(var(--surface-glass-border))]">
              {streamingText}
              <span className="inline-block w-1.5 h-4 bg-[hsl(var(--brand-500))] ml-1 animate-pulse align-middle rounded-full" />
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Unified Status Indicator */}
      {status && (
        <div
          className={cn(
            'px-3 py-2 border-t transition-all duration-300 ease-in-out',
            status.className,
            'border-[hsl(var(--surface-glass-border))]',
          )}
        >
          <div className="flex items-center gap-2">
            <StatusIcon type={status.icon} />
            <span className="text-xs truncate transition-opacity duration-300">{status.text}</span>
            {isLoading && workingTime > 3 && (
              <span className="text-xs text-[hsl(var(--neutral-500))] ml-auto shrink-0">
                ({workingTime}s)
              </span>
            )}
          </div>

          {/* Show extended message if taking too long */}
          {isLoading && workingTime > 10 && (
            <p className="text-xs text-[hsl(var(--neutral-500))] mt-1 animate-pulse">
              Still working on it... This may take a moment.
            </p>
          )}
        </div>
      )}

      {/* Input */}
      <div className="p-3 border-t border-[hsl(var(--surface-glass-border))] shrink-0 bg-[hsl(var(--surface-glass))] backdrop-blur-md">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
            placeholder="Ask about your pipeline..."
            className={cn(
              'flex-1 bg-[hsl(var(--neutral-800))] border border-[hsl(var(--surface-glass-border))]',
              'rounded-xl px-3 py-2 text-sm text-[hsl(var(--neutral-100))] placeholder-[hsl(var(--neutral-500))]',
              'transition-opacity focus:outline-none focus:border-[hsl(var(--brand-500))]',
              isLoading ? 'opacity-50' : 'opacity-100',
            )}
          />
          <button
            onClick={handleSend}
            disabled={isLoading || !input.trim()}
            className={cn(
              'flex items-center gap-1.5',
              'bg-[hsl(var(--brand-500))] hover:bg-[hsl(var(--brand-300))] text-white',
              'disabled:bg-[hsl(var(--neutral-800))] disabled:text-[hsl(var(--neutral-500))] disabled:cursor-not-allowed',
              'px-4 py-2 rounded-xl text-sm font-medium transition-colors min-w-[100px]',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[hsl(var(--brand-500))]',
            )}
          >
            {isLoading ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" strokeWidth={1.5} />
            ) : (
              <Send className="w-3.5 h-3.5" strokeWidth={1.5} />
            )}
            {getButtonLabel()}
          </button>
        </div>
      </div>
    </div>
  );
}
