import { cn } from '@/lib/utils';

interface Props {
  value: number;       // 0-100
  label: string;
  color?: string;      // Tailwind color class
  showValue?: boolean;
}

export function ProgressBar({ value, label, color = 'bg-[hsl(var(--brand-500))]', showValue = true }: Props) {
  const safeValue = Math.min(100, Math.max(0, value));
  const isLow = safeValue < 10;

  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs text-[hsl(var(--neutral-400))]">
        <span>{label}</span>
        {showValue && <span className={cn(isLow && 'text-red-400 font-bold')}>{safeValue}%</span>}
      </div>
      <div className="w-full bg-[hsl(var(--neutral-800))] rounded-full h-2">
        <div
          className={cn(
            'h-2 rounded-full transition-all duration-500',
            isLow ? 'bg-red-500' : color,
          )}
          style={{ width: `${safeValue}%` }}
        />
      </div>
    </div>
  );
}
