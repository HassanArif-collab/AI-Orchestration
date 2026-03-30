/**
 * Read-only knowledge base viewer.
 *
 * Displays the KNOWLEDGE_BASE.md file from the content_factory package.
 * This file contains style references, terminology, and production guidelines.
 */
export function KnowledgeBase() {
  return (
    <div className="p-4">
      <h3 className="text-sm font-semibold text-gray-400 mb-3">Knowledge Base</h3>
      <div className="bg-gray-800 rounded-lg p-4 text-sm text-gray-300">
        <p className="text-gray-500">
          The knowledge base contains production guidelines, style references,
          and terminology used by the content generation pipeline.
        </p>
        <p className="text-gray-500 mt-2">
          View the source at: <code className="bg-gray-900 px-1 rounded">packages/content_factory/KNOWLEDGE_BASE.md</code>
        </p>
      </div>
    </div>
  );
}
