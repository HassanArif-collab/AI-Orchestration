// apps/web/src/config/env.ts
function requireEnv(key: string): string {
  const val = import.meta.env[key];
  if (!val) throw new Error(`Missing required env variable: ${key}. Check your .env file.`);
  return val as string;
}

export const env = {
  SUPABASE_URL: requireEnv('VITE_SUPABASE_URL'),
  SUPABASE_ANON_KEY: requireEnv('VITE_SUPABASE_ANON_KEY'),
  API_BASE_URL: requireEnv('VITE_API_BASE_URL'),
};
