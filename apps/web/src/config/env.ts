// apps/web/src/config/env.ts
//
// Environment variable configuration.
//
// All vars are optional with sensible defaults. When the React app is served
// by the FastAPI backend (same origin), API_BASE_URL defaults to "" (empty
// string) which produces same-origin relative URLs (e.g. fetch("/api/...")).
// This means the app works out of the box WITHOUT a .env file when served
// from the backend.
//
// Only set VITE_API_BASE_URL if the frontend is hosted on a DIFFERENT domain
// than the API (e.g. CDN or separate web server).

function optionalEnv(key: string): string {
  return (import.meta.env[key] as string) ?? '';
}

export const env = {
  SUPABASE_URL: optionalEnv('VITE_SUPABASE_URL'),
  SUPABASE_ANON_KEY: optionalEnv('VITE_SUPABASE_ANON_KEY'),
  /** Base URL for API calls. Defaults to "" (same-origin relative URLs). */
  API_BASE_URL: optionalEnv('VITE_API_BASE_URL'),
};
