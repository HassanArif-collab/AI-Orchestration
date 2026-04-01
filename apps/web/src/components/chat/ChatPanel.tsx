import { useState, useRef, useEffect, useMemo } from 'react';
import { useChat } from '../../hooks/useChat';
import { ChatMessage } from './ChatMessage';

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
        icon: '⚠' as const,
        text: error,
        className: 'text-red-300 border-red-500/50 bg-red-900/30',
      };
    }

    if (!isLoading) return null;

    if (debouncedTools.length > 0) {
      return {
        icon: '🔧' as const,
        text: `Using tools: ${debouncedTools.join(', ')}`,
        className: 'text-blue-300 border-blue-500/50 bg-blue-900/30',
      };
    }

    if (currentStage === 'streaming' && streamingText) {
      return {
        icon: '✍️' as const,
        text: `Writing response (${streamingText.length} chars)...`,
        className: 'text-green-300 border-green-500/50 bg-green-900/30',
      };
    }

    return {
      icon: '🤖' as const,
      text: 'Thinking...',
      className: 'text-gray-400 border-gray-700 bg-gray-900/50 animate-pulse',
    };
  }, [error, isLoading, debouncedTools, currentStage, streamingText]);

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between p-3 border-b border-gray-800 shrink-0">
        <div>
          <h3 className="text-sm font-semibold text-white">Chat Assistant</h3>
          <p className="text-xs text-gray-500">Ask about your pipeline, research, or YouTube</p>
        </div>
        <button
          onClick={clearHistory}
          className="text-xs text-gray-500 hover:text-white px-2 py-1 rounded bg-gray-800"
        >
          Clear
        </button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto scrollbar-thin p-3">
        {messages.length === 0 && (
          <div className="text-center text-gray-600 text-sm mt-8">
            <p className="text-2xl mb-2">🤖</p>
            <p>Ask me anything about your content pipeline.</p>
            <div className="mt-4 space-y-1 text-xs text-gray-700">
              <p>Try: "What cards are in the pipeline?"</p>
              <p>Try: "What did we learn from past scripts?"</p>
              <p>Try: "How are competitor channels doing?"</p>
              <p>Try: "Search for Pakistan AI regulation news"</p>
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
            <div className="max-w-[80%] rounded-lg p-3 bg-gray-800 text-gray-100">
              {streamingText}
              <span className="inline-block w-2 h-5 bg-green-400 ml-1 animate-blink align-middle">
                |
              </span>
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Unified Status Indicator (single source of truth — no duplicate inline indicators) */}
      {status && (
        <div
          className={`px-3 py-2 border-t transition-all duration-300 ease-in-out ${status.className}`}
        >
          <div className="flex items-center gap-2">
            <span className="text-lg transition-all duration-300">{status.icon}</span>
            <span className="text-xs truncate transition-opacity duration-300">{status.text}</span>
            {isLoading && workingTime > 3 && (
              <span className="text-xs text-gray-500 ml-auto shrink-0">
                ({workingTime}s)
              </span>
            )}
          </div>

          {/* Show extended message if taking too long */}
          {isLoading && workingTime > 10 && (
            <p className="text-xs text-gray-500 mt-1 animate-pulse">
              Still working on it... This may take a moment.
            </p>
          )}
        </div>
      )}

      {/* Input */}
      <div className="p-3 border-t border-gray-800 shrink-0">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
            placeholder="Ask about your pipeline..."
            className={`flex-1 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 transition-opacity focus:outline-none focus:border-blue-500 ${
              isLoading ? 'opacity-50' : 'opacity-100'
            }`}
          />
          <button
            onClick={handleSend}
            disabled={isLoading || !input.trim()}
            className="bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:cursor-not-allowed text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors min-w-[100px]"
          >
            {getButtonLabel()}
          </button>
        </div>
      </div>
    </div>
  );
}
