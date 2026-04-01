import { useEffect, useState, useRef, useCallback } from 'react';
import { supabase } from '../lib/supabase';
import type { AgentThought } from '../types';

/**
 * Subscribes to real-time agent thoughts for a specific card via Supabase Realtime.
 *
 * Features:
 * - Loads full thought history on mount
 * - Subscribes to new INSERT events via WebSocket
 * - Automatic reconnection with exponential backoff (max 5 retries)
 * - Manual reconnect button exposed via forceReconnect()
 * - Shows reconnection state (connecting/reconnecting/failed)
 */
export function useAgentStream(cardId: string | null) {
  const [thoughts, setThoughts] = useState<AgentThought[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [reconnectAttempt, setReconnectAttempt] = useState(0);
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const [reconnectKey, setReconnectKey] = useState(0);
  const bottomRef = useRef<HTMLDivElement>(null);

  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const cardIdRef = useRef<string | null>(cardId);
  const channelNameRef = useRef<string | null>(null);

  // Keep cardIdRef in sync
  useEffect(() => {
    cardIdRef.current = cardId;
  }, [cardId]);

  const cleanup = useCallback(() => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
  }, []);

  useEffect(() => {
    if (!cardIdRef.current) {
      setThoughts([]);
      setIsConnected(false);
      setReconnectAttempt(0);
      setConnectionError(null);
      return cleanup;
    }

    let cancelled = false;

    const MAX_RECONNECTS = 5;
    const BASE_DELAY = 1000;

    const connect = (attempt: number) => {
      if (cancelled) return;

      const currentCardId = cardIdRef.current;
      if (!currentCardId) return;

      const channelName = `thoughts-${currentCardId}`;
      channelNameRef.current = channelName;

      // Status updates
      if (attempt > 0) {
        setReconnectAttempt(attempt);
        setConnectionError(`Reconnecting... (${attempt}/${MAX_RECONNECTS})`);
      } else {
        setReconnectAttempt(0);
        setConnectionError(null);
      }

      // Step 1: Load history
      const loadHistory = async () => {
        if (cancelled) return;
        const id = cardIdRef.current;
        if (!id) return;

        const { data, error } = await supabase
          .from('agent_thoughts')
          .select('*')
          .eq('card_id', id)
          .order('created_at', { ascending: true });

        if (!cancelled && data) {
          setThoughts(data as AgentThought[]);
        }
        if (error) {
          console.warn('Failed to load thought history:', error);
        }
      };

      loadHistory();

      // Step 2: Subscribe to new thoughts
      const channel = supabase
        .channel(channelName)
        .on(
          'postgres_changes',
          {
            event: 'INSERT',
            schema: 'public',
            table: 'agent_thoughts',
            filter: `card_id=eq.${currentCardId}`,
          },
          (payload) => {
            if (!cancelled) {
              setIsConnected(true);
              setReconnectAttempt(0);
              setConnectionError(null);
              setThoughts((prev) => [...prev, payload.new as AgentThought]);
            }
          },
        )
        .subscribe((status, _err) => {
          if (cancelled) return;

          if (status === 'SUBSCRIBED') {
            setIsConnected(true);
            setReconnectAttempt(0);
            setConnectionError(null);
          } else {
            setIsConnected(false);

            if (attempt < MAX_RECONNECTS) {
              const delay = BASE_DELAY * Math.pow(2, attempt);
              console.warn(
                `[useAgentStream] Lost connection for card ${currentCardId}. ` +
                `Retrying in ${delay / 1000}s (attempt ${attempt + 1}/${MAX_RECONNECTS})...`
              );
              setConnectionError(`Reconnecting... (${attempt + 1}/${MAX_RECONNECTS})`);

              reconnectTimerRef.current = setTimeout(() => {
                connect(attempt + 1);
              }, delay);
            } else {
              setConnectionError(
                'Connection lost after multiple attempts. Click Retry to reconnect.'
              );
            }
          }
        });
    };

    connect(0);

    return () => {
      cancelled = true;
      cleanup();
      if (channelNameRef.current) {
        supabase.removeChannel(channelNameRef.current);
        channelNameRef.current = null;
      }
      setIsConnected(false);
    };
  }, [cardId, reconnectKey, cleanup]);

  // Auto-scroll to bottom when new thoughts arrive
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [thoughts.length]);

  // Manual reconnect — removes the current channel, clears timers and state,
  // then increments reconnectKey which is in the effect's dependency array,
  // causing the effect to tear down and re-run from scratch.
  const forceReconnect = useCallback(() => {
    cleanup();
    if (channelNameRef.current) {
      supabase.removeChannel(channelNameRef.current);
      channelNameRef.current = null;
    }
    setIsConnected(false);
    setReconnectAttempt(0);
    setConnectionError(null);
    setReconnectKey((k) => k + 1);
  }, [cleanup]);

  return { thoughts, isConnected, reconnectAttempt, connectionError, bottomRef, forceReconnect };
}
