import { useEffect, useState, useRef, useCallback } from 'react';
import { supabase, isSupabaseConfigured } from '@/lib/supabase';
import type { RealtimeChannel } from '@supabase/supabase-js';
import type { AgentThought } from '@/lib/schema';

/**
 * Subscribes to real-time agent thoughts for a specific card via Supabase Realtime.
 *
 * Features:
 * - Loads full thought history on mount
 * - Subscribes to new INSERT events via WebSocket
 * - Automatic reconnection with exponential backoff (max 5 retries)
 * - Manual reconnect button exposed via forceReconnect()
 * - Shows reconnection state (connecting/reconnecting/failed)
 * - Deduplicates thoughts by ID to prevent duplicates on reconnect
 * - Properly cleans up channels before reconnecting
 * - Gracefully handles missing Supabase configuration
 *
 * NOTE: Uses `thought.content` (matching DB column name), NOT `thought.thought`.
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
  const channelRef = useRef<RealtimeChannel | null>(null);
  /** Track IDs we've already seen to prevent duplicates on reconnect */
  const seenIdsRef = useRef<Set<string>>(new Set());

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
      seenIdsRef.current = new Set();
      setIsConnected(false);
      setReconnectAttempt(0);
      setConnectionError(null);
      return cleanup;
    }

    // Guard: skip if Supabase is not configured
    if (!isSupabaseConfigured() || !supabase) {
      setConnectionError('Supabase not configured. Realtime disabled.');
      setIsConnected(false);
      return cleanup;
    }

    // Local alias — safe after the null guard above
    const db = supabase;

    let cancelled = false;
    const MAX_RECONNECTS = 5;
    const BASE_DELAY = 1000;

    const connect = (attempt: number) => {
      if (cancelled) return;

      const currentCardId = cardIdRef.current;
      if (!currentCardId) return;

      // Remove old channel before creating a new one
      if (channelRef.current) {
        db.removeChannel(channelRef.current);
        channelRef.current = null;
      }

      // Unique channel name prevents React StrictMode double-mount collisions
      const channelName = `thoughts-${currentCardId}-${Date.now()}`;

      if (attempt > 0) {
        setReconnectAttempt(attempt);
        setConnectionError(`Reconnecting... (${attempt}/${MAX_RECONNECTS})`);
      } else {
        setReconnectAttempt(0);
        setConnectionError(null);
      }

      const loadHistory = async () => {
        if (cancelled) return;
        const id = cardIdRef.current;
        if (!id) return;

        const { data, error } = await db
          .from('agent_thoughts')
          .select('*')
          .eq('card_id', id)
          .order('created_at', { ascending: true });

        if (cancelled) return;

        if (data) {
          const loadedThoughts = data as AgentThought[];
          setThoughts(loadedThoughts);
          seenIdsRef.current = new Set(loadedThoughts.map((t) => t.id));
        }
        if (error) {
          console.warn('Failed to load thought history:', error);
        }
      };

      const subscribe = () => {
        if (cancelled) return;

        const channel = db
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
              if (cancelled) return;
              const thought = payload.new as AgentThought;
              if (seenIdsRef.current.has(thought.id)) return;
              seenIdsRef.current.add(thought.id);
              setIsConnected(true);
              setReconnectAttempt(0);
              setConnectionError(null);
              setThoughts((prev) => [...prev, thought]);
            },
          )
          .subscribe((status) => {
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

        channelRef.current = channel;
      };

      loadHistory().then(() => subscribe());
    };

    connect(0);

    return () => {
      cancelled = true;
      cleanup();
      if (channelRef.current) {
        db.removeChannel(channelRef.current);
        channelRef.current = null;
      }
      setIsConnected(false);
    };
  }, [cardId, reconnectKey, cleanup]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [thoughts.length]);

  const forceReconnect = useCallback(() => {
    cleanup();
    if (channelRef.current) {
      supabase?.removeChannel(channelRef.current);
      channelRef.current = null;
    }
    setIsConnected(false);
    setReconnectAttempt(0);
    setConnectionError(null);
    setReconnectKey((k) => k + 1);
  }, [cleanup]);

  return { thoughts, isConnected, reconnectAttempt, connectionError, bottomRef, forceReconnect };
}
