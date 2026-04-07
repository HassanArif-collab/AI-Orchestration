// apps/web/src/hooks/useCards.ts
//
// SWR + Supabase Realtime hook for Kanban cards.
// This is the single source of truth for card data on the board.
//
// Architecture:
// 1. SWR fetches GET /api/kanban/cards (initial hydration + background refocus)
// 2. Supabase postgres_changes subscription fires mutate() on ANY card change
// 3. Items (Record<string, string[]>) are DERIVED from SWR cards via useEffect
// 4. Search filtering happens BEFORE item derivation (live-filters the board)
//
// CRITICAL: Items are NOT independent useState. They are derived from SWR data.
// If items were independent, they would diverge from the server after the first drag.

import { useState, useEffect } from 'react';
import useSWR from 'swr';
import { supabase, isSupabaseConfigured } from '@/lib/supabase';
import { useAppStore } from '@/lib/store';
import type { KanbanCard } from '@/lib/schema';

// Column IDs for dnd-kit — string versions of column_index (1-6)
export const COLUMNS = ['1', '2', '3', '4', '5', '6'] as const;
export type ColumnKey = (typeof COLUMNS)[number];

// All SWR data goes through the global fetcher from main.tsx SWRConfig
export function useCards() {
  const searchQuery = useAppStore((s) => s.searchQuery);
  const { data: cards, isLoading, error, mutate } = useSWR<KanbanCard[]>(
    '/api/kanban/cards',
  );

  // Derive dnd-kit items from SWR data — re-sync whenever SWR updates or search changes
  const [items, setItems] = useState<Record<ColumnKey, string[]>>(() => ({
    '1': [], '2': [], '3': [], '4': [], '5': [], '6': [],
  }));

  useEffect(() => {
    if (!cards) return;
    const filtered = cards.filter((card) =>
      !searchQuery || card.title.toLowerCase().includes(searchQuery.toLowerCase()),
    );
    setItems(
      filtered.reduce<Record<ColumnKey, string[]>>(
        (acc, card) => {
          const key = String(card.column_index) as ColumnKey;
          acc[key] = [...(acc[key] ?? []), card.id];
          return acc;
        },
        { '1': [], '2': [], '3': [], '4': [], '5': [], '6': [] },
      ),
    );
  }, [cards, searchQuery]);

  const setCards = useAppStore((s) => s.setCards);

  // Sync cards to Zustand store (for CardDrawer quick lookup)
  useEffect(() => {
    if (cards) setCards(cards);
  }, [cards, setCards]);

  // Supabase Realtime subscription — revalidates SWR on any kanban_cards change
  useEffect(() => {
    if (!isSupabaseConfigured() || !supabase) return;

    const db = supabase;

    const channelName = `kanban-realtime-${Math.random().toString(36).slice(2)}`;
    const channel = db
      .channel(channelName)
      .on(
        'postgres_changes',
        { event: '*', schema: 'public', table: 'kanban_cards' },
        () => {
          mutate(); // bound mutate from useSWR — scoped to /api/kanban/cards
        },
      )
      .subscribe();

    // CRITICAL: Always clean up channels to prevent WebSocket leaks
    return () => {
      db.removeChannel(channel);
    };
  }, [mutate]);

  return {
    cards: cards ?? [],
    items,
    setItems,
    isLoading,
    error,
    mutate,
  };
}
