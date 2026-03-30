import { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { api } from '../../lib/api';

interface SkillFile {
  name: string;
  content: string;
}

/**
 * Displays the data/skills/*.md files as read-only documents.
 *
 * CRITICAL UX RULE: "Code is Truth"
 * These prompts are loaded from Git-tracked .md files.
 * The UI explicitly shows them as READ-ONLY with a warning
 * that edits must happen in VS Code / Git — not through the UI.
 *
 * This prevents the old anti-pattern where someone edits a prompt
 * in the dashboard, it gets overwritten on next deploy, and they
 * wonder why their changes disappeared.
 */
export function SkillViewer() {
  const [skills, setSkills] = useState<SkillFile[]>([]);
  const [selectedSkill, setSelectedSkill] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.getSkills()
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
      {/* Warning banner */}
      <div className="bg-amber-900/30 border border-amber-700/50 rounded-lg p-3 mb-4">
        <p className="text-xs text-amber-400 font-medium">
          ⚠ Code is Truth — These files are read-only.
        </p>
        <p className="text-xs text-amber-400/70 mt-1">
          Edit in <code className="bg-gray-800 px-1 rounded">data/skills/*.md</code> via Git.
          Changes here would be overwritten on deploy.
        </p>
      </div>

      {/* Skill file tabs */}
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

      {/* Markdown content */}
      {activeSkill && (
        <div className="prose prose-sm prose-invert max-w-none bg-gray-800 rounded-lg p-4 max-h-[60vh] overflow-y-auto scrollbar-thin">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {activeSkill.content}
          </ReactMarkdown>
        </div>
      )}
    </div>
  );
}
