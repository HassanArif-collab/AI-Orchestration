import { useToast } from '../../hooks/useToast';

/**
 * Global toast notification container.
 * Place once near the root of the app (MainLayout).
 * Uses the global toast store so any component can trigger toasts.
 */
export function ToastContainer() {
  const { toasts, dismissToast } = useToast();

  if (toasts.length === 0) return null;

  return (
    <div className="fixed top-4 right-4 z-[100] space-y-2" role="status" aria-live="polite">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className={`
            min-w-[300px] max-w-md p-4 rounded-lg shadow-lg
            border
            ${toast.status === 'dismissing'
              ? 'animate-slide-out-right'
              : 'animate-slide-in-right'
            }
            ${toast.type === 'success' ? 'bg-green-900/90 border-green-500' : ''}
            ${toast.type === 'error' ? 'bg-red-900/90 border-red-500' : ''}
            ${toast.type === 'info' ? 'bg-blue-900/90 border-blue-500' : ''}
            ${toast.type === 'warning' ? 'bg-yellow-900/90 border-yellow-500' : ''}
          `}
        >
          <div className="flex items-start justify-between gap-2">
            <div className="flex-1">
              <p className="font-medium text-white">{toast.title}</p>
              <p className="text-sm text-white/80 mt-1">{toast.message}</p>
            </div>
            <button
              onClick={() => dismissToast(toast.id)}
              className="text-white/60 hover:text-white text-lg leading-none"
              aria-label="Dismiss"
            >
              ✕
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
