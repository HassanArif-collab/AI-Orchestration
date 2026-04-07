import { cn } from '@/lib/utils';

// ─── Skeleton Primitives ──────────────────────────────────────────────────

interface SkeletonProps {
  className?: string;
}

/**
 * Base skeleton pulse element. Renders as a rounded, pulsing block.
 */
export function Skeleton({ className }: SkeletonProps) {
  return (
    <div
      className={cn(
        'animate-pulse rounded-lg bg-[hsl(var(--neutral-800))]',
        className,
      )}
      aria-hidden="true"
    />
  );
}

// ─── Composite Skeletons ──────────────────────────────────────────────────

/**
 * Skeleton for a Kanban card — mimics the card layout with title,
 * description, and action button placeholders.
 */
export function CardSkeleton() {
  return (
    <div className="bg-[hsl(var(--surface-glass))] rounded-xl p-3 border border-[hsl(var(--surface-glass-border))] space-y-2.5">
      <Skeleton className="h-4 w-3/4" />
      <Skeleton className="h-3 w-full" />
      <Skeleton className="h-3 w-1/2" />
      <div className="flex justify-between items-center pt-1">
        <Skeleton className="h-5 w-16 rounded-full" />
        <Skeleton className="h-6 w-20 rounded-lg" />
      </div>
    </div>
  );
}

/**
 * Skeleton for a stat card (used in YouTube OwnStats, DLQ stats).
 */
export function StatSkeleton() {
  return (
    <div className="bg-[hsl(var(--surface-glass))] rounded-xl p-3 text-center border border-[hsl(var(--surface-glass-border))] space-y-2">
      <Skeleton className="h-7 w-20 mx-auto" />
      <Skeleton className="h-3 w-16 mx-auto" />
    </div>
  );
}

/**
 * Skeleton for a table row (used in Quota, ModelRegistry).
 */
export function TableRowSkeleton() {
  return (
    <div className="bg-[hsl(var(--surface-glass))] rounded-xl p-3 border border-[hsl(var(--surface-glass-border))] space-y-2">
      <div className="flex items-center justify-between">
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-4 w-16" />
      </div>
      <Skeleton className="h-3 w-3/4" />
    </div>
  );
}

/**
 * Skeleton for a competitor video card (YouTube panel).
 */
export function VideoCardSkeleton() {
  return (
    <div className="bg-[hsl(var(--surface-glass))] rounded-xl p-3 border border-[hsl(var(--surface-glass-border))] space-y-2">
      <Skeleton className="w-full aspect-video rounded-lg" />
      <Skeleton className="h-4 w-3/4" />
      <div className="flex justify-between">
        <Skeleton className="h-3 w-20" />
        <Skeleton className="h-3 w-16" />
      </div>
    </div>
  );
}
