import type { PipelineStatus } from '../../types';

const STATUS_CONFIG: Record<string, { bg: string; text: string; pulse?: boolean }> = {
  discovering: { bg: 'bg-blue-100',   text: 'text-blue-800',   pulse: true  },
  grading:     { bg: 'bg-blue-100',   text: 'text-blue-800',   pulse: true  },
  suggested:   { bg: 'bg-yellow-100', text: 'text-yellow-800'              },
  researching: { bg: 'bg-green-100',  text: 'text-green-800',  pulse: true  },
  drafting:    { bg: 'bg-purple-100', text: 'text-purple-800', pulse: true  },
  scoring:     { bg: 'bg-orange-100', text: 'text-orange-800', pulse: true  },
  mutating:    { bg: 'bg-red-100',    text: 'text-red-800',    pulse: true  },
  visuals:     { bg: 'bg-cyan-100',   text: 'text-cyan-800',   pulse: true  },
  review:      { bg: 'bg-amber-100',  text: 'text-amber-800'               },
  publishing:  { bg: 'bg-indigo-100', text: 'text-indigo-800', pulse: true  },
  complete:    { bg: 'bg-emerald-100',text: 'text-emerald-800'             },
  error:       { bg: 'bg-red-100',    text: 'text-red-800'                 },
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
