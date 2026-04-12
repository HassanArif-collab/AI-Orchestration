/**
 * Displays the final script with visual cues in a side-by-side view.
 *
 * From Phase 2d: visuals are plain text with labels like [B-ROLL], [MAP], [DATA].
 * We render them in a preformatted block — no JSON parsing needed.
 *
 * Responsive: single column on small screens, two columns on large (lg+).
 */

interface ScriptViewerProps {
  narration: string;
  visuals: string;
}

export function ScriptViewer({ narration, visuals }: ScriptViewerProps) {
  return (
    <div className="p-4">
      <h3 className="text-sm font-semibold text-[hsl(var(--neutral-400))] mb-3">
        Script with Visual Cues
      </h3>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Left: Narration */}
        <div>
          <h4 className="text-xs font-medium text-[hsl(var(--neutral-500))] mb-2 uppercase tracking-wide">
            Narration
          </h4>
          <pre className="whitespace-pre-wrap text-sm text-[hsl(var(--neutral-300))] bg-[hsl(var(--neutral-800)/0.5)] rounded-xl p-3 leading-relaxed max-h-96 overflow-y-auto border border-[hsl(var(--surface-glass-border))]">
            {narration || 'No script generated yet.'}
          </pre>
        </div>

        {/* Right: Visual Cues */}
        <div>
          <h4 className="text-xs font-medium text-[hsl(var(--neutral-500))] mb-2 uppercase tracking-wide">
            Visual Direction
          </h4>
          <pre className="whitespace-pre-wrap text-sm text-[hsl(var(--lineage-cyan))] bg-[hsl(var(--neutral-800)/0.5)] rounded-xl p-3 leading-relaxed max-h-96 overflow-y-auto border border-[hsl(var(--surface-glass-border))]">
            {visuals || 'No visual cues yet.'}
          </pre>
        </div>
      </div>
    </div>
  );
}
