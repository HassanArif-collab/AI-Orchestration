interface FriendlyError {
  title: string;
  message: string;
  action?: string;
}

interface ErrorCardProps {
  error: FriendlyError;
  onRetry?: () => void;
  onDismiss?: () => void;
}

/**
 * Reusable error display component with structured layout,
 * retry button, and optional dismiss action.
 * Uses the same visual language as other error states in the app.
 */
export function ErrorCard({ error, onRetry, onDismiss }: ErrorCardProps) {
  return (
    <div className="bg-red-900/20 border border-red-500/50 rounded-lg p-4">
      <div className="flex items-start gap-3">
        <span className="text-2xl shrink-0">⚠</span>
        <div className="flex-1 min-w-0">
          <h3 className="text-red-300 font-medium mb-1">{error.title}</h3>
          <p className="text-red-200/80 text-sm mb-3">{error.message}</p>

          {(onRetry || onDismiss) && (
            <div className="flex gap-2">
              {onRetry && error.action && (
                <button
                  onClick={onRetry}
                  className="bg-red-700 hover:bg-red-600 text-white px-4 py-2 rounded text-sm font-medium transition-colors"
                >
                  {error.action}
                </button>
              )}
              {onDismiss && (
                <button
                  onClick={onDismiss}
                  className="bg-gray-700 hover:bg-gray-600 text-white px-4 py-2 rounded text-sm font-medium transition-colors"
                >
                  Dismiss
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
