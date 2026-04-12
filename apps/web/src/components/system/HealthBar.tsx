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

  // Derive health from /api/health/services response shape:
  // { services: { zep: {operational_status, ...}, notion: {...}, freerouter: {...}, ... }, summary: {...} }
  const services = data.services ?? {};
  const summary = data.summary ?? {};
  const totalServices = summary.total ?? 0;
  const operationalCount = summary.operational ?? 0;
  const unavailableCount = summary.unavailable ?? 0;

  const allHealthy = unavailableCount === 0 && operationalCount === totalServices;

  return (
    <div className="relative" ref={tooltipRef}>
      <button
        onClick={() => setIsTooltipOpen((prev) => !prev)}
        className={cn(
          'flex items-center gap-1.5 px-2 py-1 rounded-lg text-xs font-medium transition-all duration-[var(--duration-default)]',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[hsl(var(--brand-500))]',
          allHealthy
            ? 'bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20'
            : unavailableCount > 0
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
        ) : unavailableCount > 0 ? (
          <>
            <X className="w-3 h-3" strokeWidth={1.5} />
            <span>{unavailableCount} Service{unavailableCount !== 1 ? 's' : ''} Down</span>
          </>
        ) : (
          <>
            <AlertTriangle className="w-3 h-3" strokeWidth={1.5} />
            <span>{operationalCount}/{totalServices} OK</span>
          </>
        )}
      </button>

      {/* Tooltip */}
      {isTooltipOpen && (
        <div
          className={cn(
            'absolute bottom-full left-0 mb-2 w-72 rounded-xl p-3 z-[var(--z-toast)]',
            'bg-[hsl(var(--surface-glass))] backdrop-blur-xl border border-[hsl(var(--surface-glass-border))]',
            'shadow-[var(--shadow-glass)]',
          )}
          role="tooltip"
        >
          <p className="text-[10px] font-medium tracking-wide uppercase text-[hsl(var(--neutral-400))] mb-2">
            Service Configuration
          </p>

          <div className="space-y-1.5">
            {Object.entries(services).map(([key, svc]) => {
              const status = (svc as Record<string, string>)?.operational_status ?? 'unknown';
              return (
                <div key={key} className="flex items-center justify-between text-xs">
                  <span className="text-[hsl(var(--neutral-100))] truncate mr-2 capitalize">
                    {(svc as Record<string, string>)?.name ?? key}
                  </span>
                  <span className={
                    status === 'operational' ? 'text-emerald-400' :
                    status === 'degraded' ? 'text-amber-400' :
                    'text-red-400'
                  }>
                    {status === 'operational' ? 'OK' :
                     status === 'degraded' ? 'Degraded' :
                     status === 'unavailable' ? 'Down' : '?'}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
