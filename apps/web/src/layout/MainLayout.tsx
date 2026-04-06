// apps/web/src/layout/MainLayout.tsx
//
// Primary application shell — a fixed, non-scrolling layout.
// This is the root layout structure for the entire app.
//
// Structure (from Phase 2 spec):
// <FreeRouterBanner /> — position: fixed, renders at viewport top, OUTSIDE flex flow
// <main> flex row:
//   <Sidebar> — LEFT side (w-80, glass panel, sunken surface)
//   <section> flex column:
//     <Header> — top bar (h-16, glass surface)
//     <KanbanBoard> — fills remaining space
//
// CRITICAL: FreeRouterBanner uses position: fixed — it sits outside normal
// document flow and doesn't affect the flex layout.
//
// CRITICAL: The <ErrorBoundary> wraps <App> in main.tsx. Do NOT add another one here.
//
// Styling: All colors use CSS custom properties from globals.css @theme.
// NEVER use generic bg-slate-900 or bg-gray-950.

import { cn } from '@/lib/utils';
import { Header } from './Header';
import { Sidebar } from './Sidebar';
import { Board } from '@/components/kanban/Board';
import { FreeRouterBanner } from '@/components/system/FreeRouterBanner';
import { ToastContainer } from '@/components/ui/ToastContainer';

export function MainLayout() {
  return (
    <>
      {/* FreeRouter Banner — fixed position, outside flex flow */}
      <FreeRouterBanner />

      {/* Main app shell — full viewport, no scroll */}
      <main
        className={cn(
          'flex h-screen w-full overflow-hidden font-sans',
          'bg-[hsl(var(--neutral-950))]',
          'text-[hsl(var(--neutral-100))]',
        )}
      >
        {/* Sidebar — LEFT side, fixed width glass panel */}
        <Sidebar />

        {/* Right section: Header + Content area */}
        <section className="flex flex-col h-full flex-1 min-w-0">
          {/* Header — top bar */}
          <Header />

          {/* Kanban Board — fills remaining space */}
          <Board />
        </section>
      </main>

      {/* Global toast notifications */}
      <ToastContainer />
    </>
  );
}
