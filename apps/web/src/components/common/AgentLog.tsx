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
    : 'border-l-gray-400';

  return (
    <div className={`border-l-2 ${typeBorder} pl-3 py-1.5 text-sm`}>
      <div className="flex items-center gap-2">
        <span>{thoughtDisplay?.emoji ?? '💬'}</span>
        <span className={`font-semibold ${display.colorClass}`}>
          {display.label}
        </span>
        <span className="text-gray-400 text-xs">
          {thought.created_at
            ? new Date(thought.created_at).toLocaleTimeString()
            : '—'}
        </span>
      </div>
      <p className="text-gray-300 mt-0.5 font-mono text-xs leading-relaxed">
        {thought.content}
      </p>
    </div>
  );
}
