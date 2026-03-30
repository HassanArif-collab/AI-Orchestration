import { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:3000';

export function KnowledgeBase() {
  const [content, setContent] = useState<string>('');
  const [filePath, setFilePath] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    fetch(`${API_BASE}/api/settings/knowledge-base`)
      .then((res) => res.json())
      .then((data) => {
        setContent(data.content || '');
        setFilePath(data.path || null);
      })
      .catch(console.error)
      .finally(() => setIsLoading(false));
  }, []);

  if (isLoading) return <div className="p-4 text-gray-500 text-sm">Loading knowledge base...</div>;

  return (
    <div className="p-4">
      {/* Code is Truth banner */}
      <div className="bg-amber-900/30 border border-amber-700/50 rounded-lg p-3 mb-4">
        <p className="text-xs text-amber-400 font-medium">
          ⚠ Code is Truth — Read-only view
        </p>
        {filePath && (
          <p className="text-xs text-amber-400/70 mt-1">
            Source: <code className="bg-gray-800 px-1 rounded">{filePath}</code>
          </p>
        )}
      </div>

      {/* Markdown content */}
      <div className="prose prose-sm prose-invert max-w-none bg-gray-800 rounded-lg p-4 max-h-[60vh] overflow-y-auto scrollbar-thin">
        {content ? (
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {content}
          </ReactMarkdown>
        ) : (
          <p className="text-gray-500">No knowledge base content available.</p>
        )}
      </div>
    </div>
  );
}
