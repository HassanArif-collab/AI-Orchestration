import { useState } from 'react';
import useSWR, { mutate } from 'swr';
import { AlertTriangle, RefreshCw, Trash2, Inbox } from 'lucide-react';
import type { DLQItem } from '@/types';
import { getDLQStats, getDLQItems, retryDLQItem, deleteDLQItem } from '@/lib/api';
import { mapApiError } from '@/lib/errorMapper';
import { showToast } from '@/hooks/useToast';
import { TableRowSkeleton } from '@/components/ui/Skeleton';
import { cn } from '@/lib/utils';

type DLQStatus = 'pending' | 'failed' | 'completed';

const STATUS_TABS: { id: DLQStatus; label: string }[] = [
  { id: 'pending',   label: 'Pending' },
  { id: 'failed',    label: 'Failed' },
  { id: 'completed', label: 'Completed' },
];

function formatRelativeTime(dateStr: string): string {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diffMs = now - then;

  if (diffMs < 60_000) return 'just now';
  if (diffMs < 3_600_000) return `${Math.floor(diffMs / 60_000)}m ago`;
  if (diffMs < 86_400_000) return `${Math.floor(diffMs / 3_600_000)}h ago`;
  return `${Math.floor(diffMs / 86_400_000)}d ago`;
}

function truncateText(text: string, maxLen: number): string {
  if (text.length <= maxLen) return text;
  return text.slice(0, maxLen) + '...';
}

export function DLQPanel() {
  const [statusTab, setStatusTab] = useState<DLQStatus>('pending');
  const [actionInProgress, setActionInProgress] = useState<string | null>(null);

  // Fetch stats
  const { data: stats } = useSWR('dlq-stats', () => getDLQStats());

  // Fetch items for the active status tab
  const { data: items, error: itemsError, isLoading: itemsLoading } = useSWR(
    `dlq-items-${statusTab}`,
    () => getDLQItems(statusTab) as Promise<DLQItem[]>,
  );

  const dlqItems: DLQItem[] = items ?? [];

  const handleRetry = async (itemId: string) => {
    setActionInProgress(itemId);
    try {
      await retryDLQItem(itemId);
      showToast({ type: 'success', title: 'Retry queued', message: 'The event has been re-enqueued for processing.' });
      mutate(`dlq-items-${statusTab}`);
      mutate('dlq-stats');
    } catch (err) {
      const friendlyError = mapApiError(err);
      showToast({ type: 'error', title: 'Retry failed', message: friendlyError.message });
    } finally {
      setActionInProgress(null);
    }
  };

  const handleDelete = async (itemId: string) => {
    setActionInProgress(itemId);
    try {
      await deleteDLQItem(itemId);
      showToast({ type: 'info', title: 'Item deleted', message: 'The DLQ item has been permanently removed.' });
      mutate(`dlq-items-${statusTab}`);
      mutate('dlq-stats');
    } catch (err) {
      const friendlyError = mapApiError(err);
      showToast({ type: 'error', title: 'Delete failed', message: friendlyError.message });
    } finally {
      setActionInProgress(null);
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* Stats header */}
      <div className="shrink-0 p-4 border-b border-[hsl(var(--surface-glass-border))]">
        <h3 className="text-sm font-semibold text-[hsl(var(--neutral-400))] mb-3 flex items-center gap-2">
          <AlertTriangle className="w-3.5 h-3.5" strokeWidth={1.5} />
          Dead Letter Queue
        </h3>
        <div className="flex gap-3">
          <div className="flex-1 bg-[hsl(var(--surface-glass))] rounded-lg p-2.5 border border-[hsl(var(--surface-glass-border))] text-center">
            <p className="text-lg font-semibold text-[hsl(var(--neutral-100))]">{stats?.pending ?? '—'}</p>
            <p className="text-[10px] text-[hsl(var(--neutral-500))] uppercase tracking-wider">Pending</p>
          </div>
          <div className="flex-1 bg-[hsl(var(--surface-glass))] rounded-lg p-2.5 border border-[hsl(var(--surface-glass-border))] text-center">
            <p className="text-lg font-semibold text-[hsl(var(--neutral-100))]">{stats?.total ?? '—'}</p>
            <p className="text-[10px] text-[hsl(var(--neutral-500))] uppercase tracking-wider">Total</p>
          </div>
        </div>
      </div>

      {/* Filter tabs */}
      <div className="shrink-0 flex border-b border-[hsl(var(--surface-glass-border))] bg-[hsl(var(--surface-glass))] backdrop-blur-md">
        {STATUS_TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setStatusTab(tab.id)}
            className={cn(
              'flex-1 py-2 text-xs font-medium transition-colors',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[hsl(var(--brand-500))]',
              statusTab === tab.id
                ? 'text-[hsl(var(--neutral-100))] border-b-2 border-[hsl(var(--brand-500))]'
                : 'text-[hsl(var(--neutral-500))] hover:text-[hsl(var(--neutral-300))]',
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Items list */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {itemsLoading && (
          <div className="space-y-2">
            {[1, 2, 3].map((i) => (
              <TableRowSkeleton key={i} />
            ))}
          </div>
        )}

        {itemsError && (
          <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-3">
            <p className="text-red-300 text-sm font-medium">Failed to load DLQ items</p>
            <p className="text-red-200/70 text-xs mt-1">{String(itemsError)}</p>
          </div>
        )}

        {!itemsLoading && !itemsError && dlqItems.length === 0 && (
          <div className="flex flex-col items-center justify-center py-12 text-[hsl(var(--neutral-500))]">
            <Inbox className="w-8 h-8 mb-2 opacity-50" strokeWidth={1.5} />
            <p className="text-sm">No {statusTab} items</p>
          </div>
        )}

        {!itemsLoading && !itemsError && dlqItems.map((item) => (
          <div
            key={item.id}
            className="bg-[hsl(var(--surface-glass))] rounded-xl p-3 border border-[hsl(var(--surface-glass-border))] space-y-2"
          >
            {/* Header row: event type + retries */}
            <div className="flex items-center justify-between">
              <span className="text-xs font-mono font-medium text-[hsl(var(--lineage-cyan))]">
                {item.event_type}
              </span>
              <div className="flex items-center gap-2">
                {item.retries > 0 && (
                  <span className="text-[10px] text-[hsl(var(--neutral-500))] bg-[hsl(var(--neutral-800))] px-1.5 py-0.5 rounded-md">
                    {item.retries} retry{item.retries !== 1 ? 'ies' : ''}
                  </span>
                )}
                <span className="text-[10px] text-[hsl(var(--neutral-500))]">
                  {formatRelativeTime(item.created_at)}
                </span>
              </div>
            </div>

            {/* Error message */}
            <p className="text-xs text-red-300/80 leading-relaxed">
              {truncateText(item.error_message, 120)}
            </p>

            {/* Actions */}
            {(statusTab === 'pending' || statusTab === 'failed') && (
              <div className="flex gap-2 pt-1">
                <button
                  onClick={() => handleRetry(item.id)}
                  disabled={actionInProgress === item.id}
                  className={cn(
                    'flex items-center gap-1 text-xs px-2.5 py-1 rounded-lg transition-colors',
                    'bg-blue-500/15 text-blue-400 hover:bg-blue-500/25',
                    'disabled:opacity-50 disabled:cursor-not-allowed',
                    'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[hsl(var(--brand-500))]',
                  )}
                >
                  <RefreshCw className={cn('w-3 h-3', actionInProgress === item.id && 'animate-spin')} strokeWidth={1.5} />
                  Retry
                </button>
                <button
                  onClick={() => handleDelete(item.id)}
                  disabled={actionInProgress === item.id}
                  className={cn(
                    'flex items-center gap-1 text-xs px-2.5 py-1 rounded-lg transition-colors',
                    'bg-red-500/15 text-red-400 hover:bg-red-500/25',
                    'disabled:opacity-50 disabled:cursor-not-allowed',
                    'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[hsl(var(--brand-500))]',
                  )}
                >
                  <Trash2 className="w-3 h-3" strokeWidth={1.5} />
                  Delete
                </button>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
