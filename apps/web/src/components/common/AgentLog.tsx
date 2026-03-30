import type { AgentThought } from '../../types';
import { AGENT_DISPLAY } from '../../types';

interface Props {
  thought: AgentThought;
}

export function AgentLog({ thought }: Props) {
  const display = AGENT_DISPLAY[thought.agent_name] ?? AGENT_DISPLAY.system;

  // Different styling for different thought types
  const typeBorder = {
    thinking: 'border-l-yellow-400',
    error:    'border-l-red-500',
    success:  'border-l-green-500',
    milestone:'border-l-blue-500',
    info:     'border-l-gray-400',
  }[thought.thought_type] ?? 'border-l-gray-400';

  return (
    <div className={`border-l-2 ${typeBorder} pl-3 py-1.5 text-sm`}>
      <div className="flex items-center gap-2">
        <span>{display.emoji}</span>
        <span className={`font-semibold ${display.colorClass}`}>
          {display.label}
        </span>
        <span className="text-gray-400 text-xs">
          {new Date(thought.created_at).toLocaleTimeString()}
        </span>
      </div>
      <p className="text-gray-300 mt-0.5 font-mono text-xs leading-relaxed">
        {thought.thought}
      </p>
    </div>
  );
}
