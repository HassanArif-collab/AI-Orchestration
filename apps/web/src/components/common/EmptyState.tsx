// apps/web/src/components/common/EmptyState.tsx
//
// Simple empty state placeholder for columns and panels.
// Uses Lucide icon (not emoji) per the project rules.

import { Inbox } from 'lucide-react';

interface Props {
  message: string;
}

export function EmptyState({ message }: Props) {
  return (
    <div className="flex flex-col items-center justify-center py-8 text-[hsl(var(--neutral-400))]">
      <Inbox className="w-8 h-8 mb-2 opacity-40" strokeWidth={1.5} />
      <span className="text-xs">{message}</span>
    </div>
  );
}
