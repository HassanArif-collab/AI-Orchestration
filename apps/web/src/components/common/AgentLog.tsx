// apps/web/src/components/common/AgentLog.tsx
//
// Renders a single agent thought as a console-like log entry.
// Thought type icons match the DB enum constraint exactly:
// thinking, search, output, error, memory_read, memory_write
//
// Content is rendered in <pre> with whitespace-pre-wrap to
// mitigate XSS risks without heavy sanitization.

import { cn } from '@/lib/utils';
import type { AgentThought } from '@/lib/schema';
import { AGENT_DISPLAY, THOUGHT_DISPLAY } from '@/types';

interface Props {
  thought: AgentThought;
}

export function AgentLog({ thought }: Props) {
  const display = AGENT_DISPLAY[thought.agent_name] ?? AGENT_DISPLAY.system;
  const thoughtDisplay = THOUGHT_DISPLAY[thought.thought_type];

  // Border styling based on thought type
  const typeBorder = thoughtDisplay
    ? thoughtDisplay.colorClass.replace('text-', 'border-l-')
    : 'border-l-[hsl(var(--neutral-400))]';

  return (
    <div
      className={cn(
        'border-l-2 pl-3 py-1.5',
        typeBorder,
      )}
    >
      <div className="flex items-center gap-2">
        <span className="text-sm">{thoughtDisplay?.emoji ?? '💬'}</span>
        <span className={cn('text-xs font-semibold', display.colorClass)}>
          {display.label}
        </span>
        <span className="text-[hsl(var(--neutral-400))] text-[10px] font-mono">
          {thought.created_at
            ? new Date(thought.created_at).toLocaleTimeString()
            : '—'}
        </span>
      </div>
      <pre
        className="text-[hsl(var(--neutral-400))] mt-0.5 font-mono text-xs leading-relaxed whitespace-pre-wrap"
        // pre tag mitigates XSS — no innerHTML, no dangerouslySetInnerHTML
      >
        {thought.content}
      </pre>
    </div>
  );
}
