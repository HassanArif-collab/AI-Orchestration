// apps/web/src/components/system/FreeRouterBanner.tsx
//
// FreeRouter runs the LLMs. If port 4000 is offline, the AI orchestrator fails.
// This banner polls /api/health/services every 15 seconds and displays a
// sticky red warning if FreeRouter is disconnected.
//
// CRITICAL: Uses position: fixed (NOT absolute). Absolute positions relative
// to the nearest positioned ancestor — inside a flex container it overlaps
// the header. Fixed positions relative to the viewport, ensuring it always
// sits at the true top of the screen.

import useSWR from 'swr';

export function FreeRouterBanner() {
  const { data, isLoading, error } = useSWR('/api/health/services', {
    refreshInterval: 15_000,
  });

  // Don't flash banner during initial hydration
  if (isLoading) return null;

  // Show banner if: fetch error, or freerouter explicitly offline
  if (error || data?.freerouter?.status === 'offline') {
    return (
      <div className="fixed top-0 left-0 right-0 z-[var(--z-toast)] bg-red-900/90 text-red-100 px-4 py-2 text-center text-sm backdrop-blur-sm">
        🚨 FreeRouter LLM Proxy is disconnected. Please run &lsquo;make freerouter&rsquo; in your terminal.
      </div>
    );
  }

  return null;
}
