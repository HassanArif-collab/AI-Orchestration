// apps/web/src/main.tsx
// Application Entry Point
//
// CRITICAL: globals.css MUST be the first import, before React.
// It loads Geist fonts + Tailwind @theme injection.

import './globals.css';
import React from 'react';
import ReactDOM from 'react-dom/client';
import { SWRConfig } from 'swr';
import { ErrorBoundary } from 'react-error-boundary';
import App from './App';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ErrorBoundary
      fallbackRender={({ error, resetErrorBoundary }) => (
        <div className="flex h-screen items-center justify-center bg-[hsl(var(--neutral-950))] text-[hsl(var(--neutral-100))]">
          <div className="max-w-md rounded-2xl border border-[hsl(var(--surface-glass-border))] bg-[hsl(var(--surface-glass))] backdrop-blur-xl p-8 text-center">
            <h2 className="text-lg font-semibold text-red-400 mb-2">Something went wrong</h2>
            <p className="text-sm text-[hsl(var(--neutral-400))] mb-4">
              {error instanceof Error ? error.message : 'An unexpected error occurred.'}
            </p>
            <button
              onClick={resetErrorBoundary}
              className="rounded-lg bg-[hsl(var(--brand-500))] px-4 py-2 text-sm font-medium text-white transition-all duration-300 hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[hsl(var(--brand-500))]"
            >
              Try Again
            </button>
          </div>
        </div>
      )}
    >
      <SWRConfig
        value={{
          fetcher: (url: string) =>
            fetch(url).then((res) => {
              if (!res.ok) throw new Error(res.statusText);
              return res.json();
            }),
        }}
      >
        <App />
      </SWRConfig>
    </ErrorBoundary>
  </React.StrictMode>,
);
