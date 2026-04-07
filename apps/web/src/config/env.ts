// apps/web/src/config/env.ts
//
// Environment variable configuration with Zod validation.
// Supabase vars are optional (supabase.ts handles null client gracefully).
// API base URL is required for all API calls.

function requireEnv(key: string): string {
  const val = import.meta.env[key];
  if (!val) throw new Error(`Missing required env variable: ${key}. Check your .env file.`);
  return val as string;
}

function optionalEnv(key: string): string {
  return (import.meta.env[key] as string) ?? '';
}

export const env = {
  SUPABASE_URL: optionalEnv('VITE_SUPABASE_URL'),
  SUPABASE_ANON_KEY: optionalEnv('VITE_SUPABASE_ANON_KEY'),
  API_BASE_URL: requireEnv('VITE_API_BASE_URL'),
};
