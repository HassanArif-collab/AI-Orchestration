import { useState, useEffect } from 'react';
import Markdown from 'react-markdown';
import rehypeSanitize from 'rehype-sanitize';
import { AlertTriangle } from 'lucide-react';
import { getKnowledgeBase } from '@/lib/api';
import { mapApiError } from '@/lib/errorMapper';

export function KnowledgeBase() {
  const [content, setContent] = useState<string>('');
  const [filePath, setFilePath] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadContent = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await getKnowledgeBase();
      setContent(data.content || '');
      setFilePath(data.path || null);
    } catch (err) {
      const friendlyError = mapApiError(err);
      setError(friendlyError.message);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadContent();
  }, []);

  if (isLoading) return <div className="p-4 text-[hsl(var(--neutral-400))] text-sm">Loading knowledge base...</div>;

  if (error) {
    return (
      <div className="p-4">
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-3 mb-3">
          <p className="text-red-300 text-sm font-medium">Failed to load knowledge base</p>
          <p className="text-red-200/70 text-xs mt-1">{error}</p>
        </div>
        <button
          onClick={loadContent}
          className="text-xs text-[hsl(var(--brand-300))] hover:text-[hsl(var(--brand-500))] underline"
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="p-4">
      <div className="bg-amber-500/10 border border-amber-500/30 rounded-xl p-3 mb-4">
        <p className="text-xs text-amber-400 font-medium flex items-center gap-1.5">
          <AlertTriangle className="w-3 h-3" strokeWidth={1.5} />
          Code is Truth — Read-only view
        </p>
        {filePath && (
          <p className="text-xs text-amber-400/70 mt-1">
            Source: <code className="bg-[hsl(var(--neutral-800))] px-1 rounded text-amber-300">{filePath}</code>
          </p>
        )}
      </div>

      <div className="prose prose-sm prose-invert max-w-none bg-[hsl(var(--surface-glass))] rounded-xl p-4 max-h-[60vh] overflow-y-auto border border-[hsl(var(--surface-glass-border))]">
        {content ? (
          <Markdown rehypePlugins={[rehypeSanitize]}>
            {content}
          </Markdown>
        ) : (
          <p className="text-[hsl(var(--neutral-500))]">No knowledge base content available.</p>
        )}
      </div>
    </div>
  );
}
