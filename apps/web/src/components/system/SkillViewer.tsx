import { useState, useEffect } from 'react';
import { AlertTriangle } from 'lucide-react';
import { getSkills } from '@/lib/api';
import { cn } from '@/lib/utils';

interface SkillFile {
  name: string;
  content: string;
}

export function SkillViewer() {
  const [skills, setSkills] = useState<SkillFile[]>([]);
  const [selectedSkill, setSelectedSkill] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getSkills()
      .then((res) => {
        setSkills(res.files);
        if (res.files.length > 0) setSelectedSkill(res.files[0].name);
      })
      .catch((err) => {
        console.error('Failed to load skills:', err);
        setError('Failed to load skill files');
      })
      .finally(() => setIsLoading(false));
  }, []);

  if (isLoading) return <div className="p-4 text-[hsl(var(--neutral-400))] text-sm">Loading skills...</div>;
  if (error) return <div className="p-4 text-red-400 text-sm">{error}</div>;

  const activeSkill = skills.find((s) => s.name === selectedSkill);

  return (
    <div className="p-4">
      <div className="bg-amber-500/10 border border-amber-500/30 rounded-xl p-3 mb-4">
        <p className="text-xs text-amber-400 font-medium flex items-center gap-1.5">
          <AlertTriangle className="w-3 h-3" strokeWidth={1.5} />
          Code is Truth — These files are read-only.
        </p>
        <p className="text-xs text-amber-400/70 mt-1">
          Edit in <code className="bg-[hsl(var(--neutral-800))] px-1 rounded text-amber-300">data/skills/*.md</code> via Git.
        </p>
      </div>

      <div className="flex flex-wrap gap-2 mb-4">
        {skills.map((s) => (
          <button
            key={s.name}
            onClick={() => setSelectedSkill(s.name)}
            className={cn(
              'text-xs px-3 py-1 rounded-lg transition-colors',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[hsl(var(--brand-500))]',
              selectedSkill === s.name
                ? 'bg-[hsl(var(--brand-500))] text-white'
                : 'bg-[hsl(var(--neutral-800))] text-[hsl(var(--neutral-400))] hover:text-[hsl(var(--neutral-100))] border border-[hsl(var(--surface-glass-border))]',
            )}
          >
            {s.name.replace('.md', '')}
          </button>
        ))}
      </div>

      {activeSkill && (
        <pre className="whitespace-pre-wrap font-mono bg-[hsl(var(--surface-glass))] rounded-xl p-4 max-h-[60vh] overflow-y-auto text-xs text-[hsl(var(--neutral-300))] border border-[hsl(var(--surface-glass-border))]">
          {activeSkill.content}
        </pre>
      )}
    </div>
  );
}
