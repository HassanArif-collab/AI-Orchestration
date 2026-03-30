import { useEffect, useState, useRef } from 'react';
import { supabase } from '../lib/supabase';
import type { AgentThought } from '../types';

/**
 * Subscribes to real-time agent thoughts for a specific card.
 *
 * When the CardDrawer opens for card "abc-123", this hook:
 * 1. Fetches ALL existing thoughts for that card (history)
 * 2. Opens a WebSocket subscription for NEW thoughts
 * 3. Appends new thoughts to the list as they arrive
 * 4. Cleans up the subscription when the drawer closes
 *
 * The UI gets instant updates — no polling, no lag.
 */
export function useAgentStream(cardId: string | null) {
  const [thoughts, setThoughts] = useState<AgentThought[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!cardId) {
      setThoughts([]);
      return;
    }

    let cancelled = false;

    // Step 1: Load history
    const loadHistory = async () => {
      const { data, error } = await supabase
        .from('agent_thoughts')
        .select('*')
        .eq('card_id', cardId)
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
      .channel(`thoughts-${cardId}`)
      .on(
        'postgres_changes',
        {
          event: 'INSERT',
          schema: 'public',
          table: 'agent_thoughts',
          filter: `card_id=eq.${cardId}`,
        },
        (payload) => {
          if (!cancelled) {
            setThoughts((prev) => [...prev, payload.new as AgentThought]);
          }
        }
      )
      .subscribe((status) => {
        setIsConnected(status === 'SUBSCRIBED');
      });

    return () => {
      cancelled = true;
      supabase.removeChannel(channel);
      setIsConnected(false);
    };
  }, [cardId]);

  // Auto-scroll to bottom when new thoughts arrive
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [thoughts.length]);

  return { thoughts, isConnected, bottomRef };
}
