import { useState, useEffect } from 'react';
import { getSkills } from '@/lib/api';

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

  if (isLoading) return <div className="p-4 text-gray-500 text-sm">Loading skills...</div>;
  if (error) return <div className="p-4 text-red-400 text-sm">{error}</div>;

  const activeSkill = skills.find((s) => s.name === selectedSkill);

  return (
    <div className="p-4">
      <div className="bg-amber-900/30 border border-amber-700/50 rounded-lg p-3 mb-4">
        <p className="text-xs text-amber-400 font-medium">
          ⚠ Code is Truth — These files are read-only.
        </p>
        <p className="text-xs text-amber-400/70 mt-1">
          Edit in <code className="bg-gray-800 px-1 rounded">data/skills/*.md</code> via Git.
        </p>
      </div>

      <div className="flex flex-wrap gap-2 mb-4">
        {skills.map((s) => (
          <button
            key={s.name}
            onClick={() => setSelectedSkill(s.name)}
            className={`text-xs px-3 py-1 rounded ${
              selectedSkill === s.name
                ? 'bg-blue-600 text-white'
                : 'bg-gray-800 text-gray-400 hover:text-white'
            }`}
          >
            {s.name.replace('.md', '')}
          </button>
        ))}
      </div>

      {activeSkill && (
        <pre className="whitespace-pre-wrap font-mono bg-gray-800 rounded-lg p-4 max-h-[60vh] overflow-y-auto scrollbar-thin text-xs text-gray-300">
          {activeSkill.content}
        </pre>
      )}
    </div>
  );
}
