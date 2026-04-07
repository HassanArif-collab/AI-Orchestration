import { useState, useCallback, useRef } from 'react';
import { mapApiError } from '../lib/errorMapper';
import { SSE_TIMEOUT_MS } from '@/lib/constants';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:3000';

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'tool';
  content: string;
  toolName?: string;
  timestamp: Date;
}

export type ChatStage = 'idle' | 'sending' | 'streaming' | 'tools' | 'done' | 'error';

interface UseChatReturn {
  messages: ChatMessage[];
  isLoading: boolean;
  activeTools: string[];
  currentStage: ChatStage;
  streamingText: string;
  error: string | null;
  sendMessage: (text: string) => Promise<void>;
  clearHistory: () => void;
  sessionId: string;
}

/**
 * Hook for managing chat state with streaming responses.
 *
 * Uses the /api/chat/stream SSE endpoint for real-time token streaming.
 * Conversation persists via session_id stored in LangGraph checkpointer.
 *
 * Enhanced with stage tracking for rich UX feedback.
 */
export function useChat(): UseChatReturn {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [activeTools, setActiveTools] = useState<string[]>([]);
  const [currentStage, setCurrentStage] = useState<ChatStage>('idle');
  const [streamingText, setStreamingText] = useState('');
  const [error, setError] = useState<string | null>(null);
  const sessionRef = useRef<string>(crypto.randomUUID());
  const abortRef = useRef<AbortController | null>(null);

  const sendMessage = useCallback(async (text: string) => {
    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: text,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setIsLoading(true);
    setCurrentStage('sending');
    setActiveTools([]);
    setStreamingText('');
    setError(null);

    // Placeholder for the streaming assistant response
    const assistantId = crypto.randomUUID();
    const assistantMsg: ChatMessage = {
      id: assistantId,
      role: 'assistant',
      content: '',
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, assistantMsg]);

    const controller = new AbortController();
    abortRef.current = controller;

    const sseTimedOut = { current: false };
    const sseTimeoutId = setTimeout(() => {
      sseTimedOut.current = true;
      controller.abort();
    }, SSE_TIMEOUT_MS);

    try {
      const response = await fetch(`${API_BASE}/api/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: text,
          session_id: sessionRef.current,
        }),
        signal: controller.signal,
      });

      if (!response.ok) {
        const errorBody = await response.text().catch(() => '');
        throw new Error(`API ${response.status}: ${errorBody}`);
      }
      if (!response.body) throw new Error('No response body');

      // Transition from 'sending' to 'streaming' once we start receiving
      setCurrentStage('streaming');

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let accumulatedText = '';

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
              case 'token': {
                accumulatedText += event.content;
                setStreamingText(accumulatedText);
                setCurrentStage('streaming');
                break;
              }

              case 'tool_start': {
                setActiveTools((prev) => [...prev, event.tool]);
                setCurrentStage('tools');
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
              }

              case 'tool_end': {
                setActiveTools((prev) => prev.filter((t) => t !== event.tool));
                // If no more tools active, go back to streaming stage
                break;
              }

              case 'done': {
                if (event.session_id) {
                  sessionRef.current = event.session_id;
                }
                // Finalize: write accumulated text into the assistant message
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === assistantId
                      ? { ...m, content: accumulatedText || m.content }
                      : m
                  )
                );
                setCurrentStage('done');
                break;
              }

              case 'error': {
                setCurrentStage('error');
                setError(event.message || 'An error occurred');
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === assistantId
                      ? { ...m, content: `Error: ${event.message}` }
                      : m
                  )
                );
                break;
              }
            }
          } catch {
            // Skip malformed JSON lines
          }
        }
      }
    } catch (err) {
      if (controller.signal.aborted) {
        if (sseTimedOut.current) {
          const timeoutErr = new Error('API 408: SSE stream timed out');
          const friendlyError = mapApiError(timeoutErr);
          setError(friendlyError.message);
          setCurrentStage('error');
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? { ...m, content: `${friendlyError.title}: ${friendlyError.message}` }
                : m
            )
          );
        }
        return;
      }
      const friendlyError = mapApiError(err);
      setError(friendlyError.message);
      setCurrentStage('error');
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId
            ? { ...m, content: `${friendlyError.title}: ${friendlyError.message}` }
            : m
        )
      );
    } finally {
      clearTimeout(sseTimeoutId);
      abortRef.current = null;
      if (!controller.signal.aborted) {
        setIsLoading(false);
        setActiveTools([]);
        setStreamingText('');
        // Reset stage to idle after a short delay (allows UI to show 'done' briefly)
        setTimeout(() => {
          setCurrentStage((prev) => (prev === 'done' ? 'idle' : prev));
        }, 1000);
      }
    }
  }, []);

  const clearHistory = useCallback(() => {
    // Abort any in-flight SSE stream
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
    setMessages([]);
    setActiveTools([]);
    setCurrentStage('idle');
    setStreamingText('');
    setError(null);
    setIsLoading(false);
    sessionRef.current = crypto.randomUUID();
  }, []);

  return {
    messages,
    isLoading,
    activeTools,
    currentStage,
    streamingText,
    error,
    sendMessage,
    clearHistory,
    sessionId: sessionRef.current,
  };
}
