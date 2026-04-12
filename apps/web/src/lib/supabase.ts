// apps/web/src/lib/supabase.ts
// Supabase Client Singleton
//
// This is the ONLY place createClient is called.
// All hooks and components must import this singleton.
// Never call createClient inside hooks or components — that would
// create duplicate WebSocket connections.
//
// When VITE_SUPABASE_URL or VITE_SUPABASE_ANON_KEY are missing,
// `supabase` is `null` and `isSupabaseConfigured()` returns false.
// Components that need Supabase MUST check this before using the client.

import { createClient, type SupabaseClient } from '@supabase/supabase-js';

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

function buildClient(): SupabaseClient | null {
  if (!supabaseUrl || !supabaseAnonKey) return null;
  return createClient(supabaseUrl, supabaseAnonKey, {
    realtime: {
      params: { eventsPerSecond: 10 }, // throttle realtime events to prevent WebSocket flood
    },
  });
}

/** Supabase client — `null` when credentials are not configured. */
export const supabase: SupabaseClient | null = buildClient();

/** Returns `true` when Supabase credentials are available. */
export function isSupabaseConfigured(): boolean {
  return supabase !== null;
}
