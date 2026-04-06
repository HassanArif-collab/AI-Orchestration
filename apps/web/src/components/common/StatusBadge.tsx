import type { KanbanCard } from '@/lib/schema';

// Status values matching the DB constraint in KanbanCardSchema
type CardStatus = KanbanCard['status'];

const STATUS_CONFIG: Record<string, { bg: string; text: string; pulse?: boolean }> = {
  idle:            { bg: 'bg-gray-700/50',    text: 'text-gray-300'                },
  processing:      { bg: 'bg-blue-900/50',    text: 'text-blue-300',   pulse: true  },
  error:           { bg: 'bg-red-900/50',     text: 'text-red-300'                 },
  review_required: { bg: 'bg-amber-900/50',   text: 'text-amber-300'               },
  completed:       { bg: 'bg-emerald-900/50', text: 'text-emerald-300'             },
};

interface Props {
  status: CardStatus;
}

export function StatusBadge({ status }: Props) {
  const config = STATUS_CONFIG[status] ?? STATUS_CONFIG.error;

  return (
    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium ${config.bg} ${config.text}`}>
      {config.pulse && (
        <span className="relative flex h-2 w-2">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-current opacity-75" />
          <span className="relative inline-flex rounded-full h-2 w-2 bg-current" />
        </span>
      )}
      {status}
    </span>
  );
}
