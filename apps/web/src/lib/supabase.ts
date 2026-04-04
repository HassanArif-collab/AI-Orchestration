import { createClient, SupabaseClient } from '@supabase/supabase-js';

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
const supabaseKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

const _isConfigured = Boolean(supabaseUrl && supabaseKey);

if (!_isConfigured) {
  console.warn(
    'Missing VITE_SUPABASE_URL or VITE_SUPABASE_ANON_KEY in .env file.\n' +
    'Copy apps/web/.env.example to apps/web/.env and fill in your Supabase credentials.'
  );
}

export const supabase: SupabaseClient | null = _isConfigured
  ? createClient(supabaseUrl!, supabaseKey!, {
      realtime: {
        params: {
          // Only listen for INSERT events on agent_thoughts
          // This reduces bandwidth compared to listening to all events
          eventsPerSecond: 10,
        },
      },
    })
  : null;

export function isSupabaseConfigured(): boolean {
  return _isConfigured;
}
