// apps/web/src/components/common/StatusBadge.tsx
//
// Displays card status as a small badge with optional pulse indicator.
// Uses glassmorphism CSS variables.

import { cn } from '@/lib/utils';
import type { KanbanCard } from '@/lib/schema';

type CardStatus = KanbanCard['status'];

const STATUS_CONFIG: Record<string, { bg: string; text: string; pulse?: boolean }> = {
  idle:            { bg: 'bg-[hsl(var(--neutral-800)/0.6)]',   text: 'text-[hsl(var(--neutral-400))]' },
  processing:      { bg: 'bg-[hsl(var(--brand-500)/0.15)]',    text: 'text-[hsl(var(--brand-300))]', pulse: true },
  error:           { bg: 'bg-red-500/15',                      text: 'text-red-400' },
  review_required: { bg: 'bg-amber-500/15',                    text: 'text-amber-400' },
  completed:       { bg: 'bg-emerald-500/15',                  text: 'text-emerald-400' },
};

interface Props {
  status: CardStatus;
}

export function StatusBadge({ status }: Props) {
  const config = STATUS_CONFIG[status] ?? STATUS_CONFIG.error;

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-medium tracking-wide uppercase',
        config.bg,
        config.text,
      )}
    >
      {config.pulse && (
        <span className="relative flex h-1.5 w-1.5">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-current opacity-75" />
          <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-current" />
        </span>
      )}
      {status}
    </span>
  );
}
