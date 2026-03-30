import { useState, useRef, useEffect } from 'react';
import { useChat } from '../../hooks/useChat';
import { ChatMessage } from './ChatMessage';

export function ChatPanel() {
  const { messages, isLoading, activeTools, sendMessage, clearHistory } = useChat();
  const [input, setInput] = useState('');
  const bottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages.length]);

  const handleSend = async () => {
    const text = input.trim();
    if (!text || isLoading) return;
    setInput('');
    await sendMessage(text);
  };

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

        {/* Active tool indicators */}
        {activeTools.length > 0 && (
          <div className="flex justify-start mb-2">
            <div className="bg-gray-800 rounded-lg px-4 py-2 text-xs text-gray-400">
              <span className="animate-pulse">Using:</span>{' '}
              {activeTools.join(', ')}
            </div>
          </div>
        )}

        {/* Loading indicator */}
        {isLoading && activeTools.length === 0 && (
          <div className="flex justify-start mb-2">
            <div className="bg-gray-800 rounded-lg px-4 py-2">
              <span className="animate-pulse text-gray-400 text-sm">Thinking...</span>
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="p-3 border-t border-gray-800 shrink-0">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
            placeholder="Ask about your pipeline..."
            disabled={isLoading}
            className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 disabled:opacity-50"
          />
          <button
            onClick={handleSend}
            disabled={isLoading || !input.trim()}
            className="bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 text-white px-4 py-2 rounded-lg text-sm font-medium"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}
