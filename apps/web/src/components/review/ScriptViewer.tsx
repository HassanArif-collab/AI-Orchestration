interface Props {
  narration: string;
  visuals: string;
}

/**
 * Displays the final script with visual cues in a side-by-side view.
 *
 * From Phase 2d: visuals are plain text with labels like [B-ROLL], [MAP], [DATA].
 * We render them in a preformatted block — no JSON parsing needed.
 */
export function ScriptViewer({ narration, visuals }: Props) {
  return (
    <div className="p-4">
      <h3 className="text-sm font-semibold text-gray-400 mb-3">
        📝 Script with Visual Cues
      </h3>

      <div className="grid grid-cols-2 gap-4">
        {/* Left: Narration */}
        <div>
          <h4 className="text-xs font-medium text-gray-500 mb-2 uppercase tracking-wide">
            Narration
          </h4>
          <pre className="whitespace-pre-wrap text-sm text-gray-300 bg-gray-800 rounded p-3 leading-relaxed max-h-96 overflow-y-auto scrollbar-thin">
            {narration || 'No script generated yet.'}
          </pre>
        </div>

        {/* Right: Visual Cues */}
        <div>
          <h4 className="text-xs font-medium text-gray-500 mb-2 uppercase tracking-wide">
            Visual Direction
          </h4>
          <pre className="whitespace-pre-wrap text-sm text-cyan-300 bg-gray-800 rounded p-3 leading-relaxed max-h-96 overflow-y-auto scrollbar-thin">
            {visuals || 'No visual cues yet.'}
          </pre>
        </div>
      </div>
    </div>
  );
}
