// apps/web/src/lib/supabase.ts
// Supabase Client Singleton
//
// This is the ONLY place createClient is called.
// All hooks and components must import this singleton.
// Never call createClient inside hooks or components — that would
// create duplicate WebSocket connections.

import { createClient } from '@supabase/supabase-js';
import { env } from '@/config/env';

export const supabase = createClient(env.SUPABASE_URL, env.SUPABASE_ANON_KEY, {
  realtime: {
    params: { eventsPerSecond: 10 }, // throttle realtime events to prevent WebSocket flood
  },
});
