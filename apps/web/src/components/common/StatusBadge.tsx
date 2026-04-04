import type { PipelineStatus } from '../../types';

const STATUS_CONFIG: Record<string, { bg: string; text: string; pulse?: boolean }> = {
  discovering: { bg: 'bg-blue-900/50',   text: 'text-blue-300',   pulse: true  },
  grading:     { bg: 'bg-blue-900/50',   text: 'text-blue-300',   pulse: true  },
  suggested:   { bg: 'bg-yellow-900/50', text: 'text-yellow-300'              },
  researching: { bg: 'bg-green-900/50',  text: 'text-green-300',  pulse: true  },
  drafting:    { bg: 'bg-purple-900/50', text: 'text-purple-300', pulse: true  },
  scoring:     { bg: 'bg-orange-900/50', text: 'text-orange-300', pulse: true  },
  mutating:    { bg: 'bg-red-900/50',    text: 'text-red-300',    pulse: true  },
  visuals:     { bg: 'bg-cyan-900/50',   text: 'text-cyan-300',   pulse: true  },
  review:      { bg: 'bg-amber-900/50',  text: 'text-amber-300'               },
  publishing:  { bg: 'bg-indigo-900/50', text: 'text-indigo-300', pulse: true  },
  complete:    { bg: 'bg-emerald-900/50',text: 'text-emerald-300'             },
  error:       { bg: 'bg-red-900/50',    text: 'text-red-300'                 },
};

interface Props {
  status: PipelineStatus;
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
