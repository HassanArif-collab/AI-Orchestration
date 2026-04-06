// apps/web/src/components/system/HealthBar.tsx
//
// Displays backend service health status as a small badge.
// Polled every 30 seconds via SWR (slower than FreeRouterBanner since
// this is informational, not critical-path).
//
// Response shape from /api/health/services:
// {
//   "critical": { "FREEROUTER_URL": true },
//   "optional": { "NOTION_API_KEY": true, "ZEP_API_KEY": false, "EXA_API_KEY": true },
//   "missing_critical": [],
//   "missing_optional": ["ZEP_API_KEY"]
// }
//
// Logic:
// - All critical services true → green dot
// - Any optional missing → yellow warning badge "N/M Services Configured"
// - Clicking the badge opens a tooltip listing exact missing integrations

import { useState, useRef, useEffect, useCallback } from 'react';
import useSWR from 'swr';
import { AlertTriangle, Check, X } from 'lucide-react';
import { cn } from '@/lib/utils';

export function HealthBar() {
  const { data, isLoading } = useSWR('/api/health/services', {
    refreshInterval: 30_000,
  });

  const [isTooltipOpen, setIsTooltipOpen] = useState(false);
  const tooltipRef = useRef<HTMLDivElement>(null);

  // Close tooltip on click outside
  const handleClickOutside = useCallback((e: MouseEvent) => {
    if (tooltipRef.current && !tooltipRef.current.contains(e.target as Node)) {
      setIsTooltipOpen(false);
    }
  }, []);

  useEffect(() => {
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [handleClickOutside]);

  // Close tooltip on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setIsTooltipOpen(false);
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, []);

  if (isLoading || !data) return null;

  const hasMissingOptional = data.missing_optional?.length > 0;
  const hasMissingCritical = data.missing_critical?.length > 0;

  // Count configured services
  const totalOptional = Object.keys(data.optional ?? {}).length;
  const configuredOptional = totalOptional - (data.missing_optional?.length ?? 0);
  const totalCritical = Object.keys(data.critical ?? {}).length;
  const configuredCritical = totalCritical - (data.missing_critical?.length ?? 0);

  const allHealthy = !hasMissingCritical && !hasMissingOptional;

  return (
    <div className="relative" ref={tooltipRef}>
      <button
        onClick={() => setIsTooltipOpen((prev) => !prev)}
        className={cn(
          'flex items-center gap-1.5 px-2 py-1 rounded-lg text-xs font-medium transition-all duration-[var(--duration-default)]',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[hsl(var(--brand-500))]',
          allHealthy
            ? 'bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20'
            : hasMissingCritical
              ? 'bg-red-500/10 text-red-400 hover:bg-red-500/20'
              : 'bg-amber-500/10 text-amber-400 hover:bg-amber-500/20',
        )}
        aria-label="Service health status"
      >
        {allHealthy ? (
          <>
            <Check className="w-3 h-3" strokeWidth={1.5} />
            <span>All Services OK</span>
          </>
        ) : hasMissingCritical ? (
          <>
            <X className="w-3 h-3" strokeWidth={1.5} />
            <span>Critical Missing</span>
          </>
        ) : (
          <>
            <AlertTriangle className="w-3 h-3" strokeWidth={1.5} />
            <span>{configuredOptional + configuredCritical}/{totalOptional + totalCritical} Configured</span>
          </>
        )}
      </button>

      {/* Tooltip */}
      {isTooltipOpen && (
        <div
          className={cn(
            'absolute bottom-full left-0 mb-2 w-64 rounded-xl p-3 z-[var(--z-toast)]',
            'bg-[hsl(var(--surface-glass))] backdrop-blur-xl border border-[hsl(var(--surface-glass-border))]',
            'shadow-[var(--shadow-glass)]',
          )}
          role="tooltip"
        >
          <p className="text-[10px] font-medium tracking-wide uppercase text-[hsl(var(--neutral-400))] mb-2">
            Service Configuration
          </p>

          {/* Critical Services */}
          <div className="space-y-1 mb-2">
            {Object.entries(data.critical ?? {}).map(([key, configured]) => (
              <div key={key} className="flex items-center justify-between text-xs">
                <span className="text-[hsl(var(--neutral-100))] truncate mr-2">
                  {key.replace(/_/g, ' ')}
                </span>
                <span className={configured ? 'text-emerald-400' : 'text-red-400'}>
                  {configured ? '✓' : '✗'}
                </span>
              </div>
            ))}
          </div>

          {/* Optional Services */}
          {Object.keys(data.optional ?? {}).length > 0 && (
            <>
              <div className="border-t border-[hsl(var(--surface-glass-border))] my-2" />
              <p className="text-[10px] font-medium tracking-wide uppercase text-[hsl(var(--neutral-400))] mb-1">
                Optional Integrations
              </p>
              <div className="space-y-1">
                {Object.entries(data.optional ?? {}).map(([key, configured]) => (
                  <div key={key} className="flex items-center justify-between text-xs">
                    <span className="text-[hsl(var(--neutral-100))] truncate mr-2">
                      {key.replace(/_/g, ' ')}
                    </span>
                    <span className={configured ? 'text-emerald-400' : 'text-amber-400'}>
                      {configured ? '✓' : '✗'}
                    </span>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
