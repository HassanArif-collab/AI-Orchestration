import { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { api } from '../../lib/api';
import { mapApiError } from '../../lib/errorMapper';

export function KnowledgeBase() {
  const [content, setContent] = useState<string>('');
  const [filePath, setFilePath] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadContent = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await api.getKnowledgeBase();
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

  if (isLoading) return <div className="p-4 text-gray-500 text-sm">Loading knowledge base...</div>;

  if (error) {
    return (
      <div className="p-4">
        <div className="bg-red-900/30 border border-red-500/50 rounded-lg p-3 mb-3">
          <p className="text-red-300 text-sm font-medium">Failed to load knowledge base</p>
          <p className="text-red-200/70 text-xs mt-1">{error}</p>
        </div>
        <button
          onClick={loadContent}
          className="text-xs text-blue-400 hover:text-blue-300 underline"
        >
          Retry
        </button>
      </div>
    );
  }

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
