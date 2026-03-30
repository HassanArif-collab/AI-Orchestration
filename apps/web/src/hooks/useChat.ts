import { useState, useCallback, useRef } from 'react';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:3000';

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'tool';
  content: string;
  toolName?: string;
  timestamp: Date;
}

interface UseChatReturn {
  messages: ChatMessage[];
  isLoading: boolean;
  activeTools: string[];
  sendMessage: (text: string) => Promise<void>;
  clearHistory: () => void;
  sessionId: string;
}

/**
 * Hook for managing chat state with streaming responses.
 *
 * Uses the /api/chat/stream SSE endpoint for real-time token streaming.
 * Conversation persists via session_id stored in LangGraph checkpointer.
 */
export function useChat(): UseChatReturn {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [activeTools, setActiveTools] = useState<string[]>([]);
  const sessionRef = useRef<string>(crypto.randomUUID());

  const sendMessage = useCallback(async (text: string) => {
    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: text,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setIsLoading(true);
    setActiveTools([]);

    // Placeholder for the streaming assistant response
    const assistantId = crypto.randomUUID();
    const assistantMsg: ChatMessage = {
      id: assistantId,
      role: 'assistant',
      content: '',
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, assistantMsg]);

    try {
      const response = await fetch(`${API_BASE}/api/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: text,
          session_id: sessionRef.current,
        }),
      });

      if (!response.ok) throw new Error(`Chat API returned ${response.status}`);
      if (!response.body) throw new Error('No response body');

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const jsonStr = line.slice(6).trim();
          if (!jsonStr) continue;

          try {
            const event = JSON.parse(jsonStr);

            switch (event.type) {
              case 'token':
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === assistantId
                      ? { ...m, content: m.content + event.content }
                      : m
                  )
                );
                break;

              case 'tool_start':
                setActiveTools((prev) => [...prev, event.tool]);
                setMessages((prev) => [
                  ...prev,
                  {
                    id: crypto.randomUUID(),
                    role: 'tool' as const,
                    content: `Calling ${event.tool}...`,
                    toolName: event.tool,
                    timestamp: new Date(),
                  },
                ]);
                break;

              case 'tool_end':
                setActiveTools((prev) => prev.filter((t) => t !== event.tool));
                break;

              case 'done':
                if (event.session_id) {
                  sessionRef.current = event.session_id;
                }
                break;

              case 'error':
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === assistantId
                      ? { ...m, content: `Error: ${event.message}` }
                      : m
                  )
                );
                break;
            }
          } catch {
            // Skip malformed JSON lines
          }
        }
      }
    } catch (err) {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId
            ? { ...m, content: `Failed to connect: ${err}` }
            : m
        )
      );
    } finally {
      setIsLoading(false);
      setActiveTools([]);
    }
  }, []);

  const clearHistory = useCallback(() => {
    setMessages([]);
    sessionRef.current = crypto.randomUUID();
  }, []);

  return {
    messages,
    isLoading,
    activeTools,
    sendMessage,
    clearHistory,
    sessionId: sessionRef.current,
  };
}
