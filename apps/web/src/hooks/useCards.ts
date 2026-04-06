import useSWR from 'swr';
import { supabase } from '@/lib/supabase';
import type { KanbanCard } from '@/lib/schema';
import { useEffect } from 'react';

/**
 * Fetches all kanban cards from Supabase and subscribes to realtime changes.
 * When a card is inserted, updated, or deleted in Supabase, this hook
 * automatically refetches — no polling needed.
 *
 * Returns: { cards, isLoading, error, mutate }
 *   - cards: KanbanCard[] grouped by nothing (caller groups by column)
 *   - mutate: call to force refetch after local actions
 */
export function useCards() {
  const fetcher = async (): Promise<KanbanCard[]> => {
    const { data, error } = await supabase
      .from('kanban_cards')
      .select('*')
      .order('created_at', { ascending: false });

    if (error) throw error;
    return data as KanbanCard[];
  };

  const { data: cards, error, isLoading, mutate } = useSWR('kanban-cards', fetcher);

  // Subscribe to realtime changes on kanban_cards table
  useEffect(() => {
    // Unique channel name prevents React StrictMode double-mount collisions
    const channelName = `kanban-realtime-${Math.random().toString(36).slice(2)}`;
    const channel = supabase
      .channel(channelName)
      .on(
        'postgres_changes',
        { event: '*', schema: 'public', table: 'kanban_cards' },
        () => {
          // Any change to kanban_cards → refetch all cards
          mutate();
        }
      )
      .subscribe();

    // CRITICAL: Always clean up channels to prevent WebSocket leaks
    return () => {
      supabase.removeChannel(channel);
    };
  }, [mutate]);

  return { cards: cards ?? [], isLoading, error, mutate };
}

/**
 * Helper: group cards by column_index number
 */
export function groupByColumn(cards: KanbanCard[]): Record<number, KanbanCard[]> {
  const grouped: Record<number, KanbanCard[]> = { 1: [], 2: [], 3: [], 4: [], 5: [], 6: [] };
  for (const card of cards) {
    const col = card.column_index;
    if (grouped[col]) {
      grouped[col].push(card);
    }
  }
  return grouped;
}
