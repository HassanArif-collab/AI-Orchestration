// apps/web/src/layout/Sidebar.tsx
//
// Right-side panel with tabbed panels for Chat, DLQ, Quota, YouTube, and Settings/Skills.
//
// CRITICAL RULE: Do NOT conditionally render tabs out of the DOM.
// E.g., `activeTab === 'chat' ? <ChatPanel /> : null` is STRICTLY FORBIDDEN.
// Why? The Chat Panel maintains an active SSE streaming connection.
// If unmounted, the connection drops, stream is broken, and session is destroyed.
// Instead, use CSS: className={activeTab === 'chat' ? 'flex' : 'hidden'}
//
// Styling directives (from Phase 2 spec):
// - Glass Panel: bg-[hsl(var(--surface-sunken))] + backdrop-blur-2xl
// - Border: border-[hsl(var(--surface-glass-border))]
// - Z-index: z-[var(--z-sidebar)]
// - Width: w-80
// - Position: RIGHT side of layout (fixed, non-scrolling app shell)
//
// Sidebar tabs:
// 1. Chat (AI Assistant)
// 2. DLQ (Dead Letter Queue & Retries)
// 3. Quota (RPM/TPM monitors)
// 4. YouTube (Competitor Analytics)
// 5. Settings / Skills (Knowledge Base)

import { useCallback, useRef } from 'react';
import {
  MessageSquare,
  AlertCircle,
  BarChart3,
  Youtube,
  Settings,
  PanelRightClose,
  PanelRightOpen,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAppStore } from '@/lib/store';
import { ChatPanel } from '@/components/chat/ChatPanel';
import { YouTubePanel } from '@/components/youtube/YouTubePanel';
import { QuotaPanel } from '@/components/telemetry/QuotaPanel';
import { ModelRegistry } from '@/components/telemetry/ModelRegistry';
import { SkillViewer } from '@/components/system/SkillViewer';
import { KnowledgeBase } from '@/components/system/KnowledgeBase';
import { DLQPanel } from '@/components/dlq/DLQPanel';

type SidebarTab = 'chat' | 'dlq' | 'quota' | 'youtube' | 'settings';

const TAB_CONFIG: { id: SidebarTab; label: string; icon: typeof MessageSquare }[] = [
  { id: 'chat',     label: 'Chat',     icon: MessageSquare },
  { id: 'dlq',      label: 'DLQ',      icon: AlertCircle },
  { id: 'quota',    label: 'Quota',    icon: BarChart3 },
  { id: 'youtube',  label: 'YouTube',  icon: Youtube },
  { id: 'settings', label: 'Settings', icon: Settings },
];

export function Sidebar() {
  const activeTab = useAppStore((s) => s.activeTab ?? 'chat');
  const isSidebarOpen = useAppStore((s) => s.isSidebarOpen);
  const toggleSidebar = useAppStore((s) => s.toggleSidebar);
  const tablistRef = useRef<HTMLDivElement>(null);

  // Arrow key navigation for tabs (accessibility)
  const handleTablistKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;

    const currentIndex = TAB_CONFIG.findIndex((t) => t.id === activeTab);
    let nextIndex: number;

    if (e.key === 'ArrowRight') {
      nextIndex = currentIndex < TAB_CONFIG.length - 1 ? currentIndex + 1 : 0;
    } else {
      nextIndex = currentIndex > 0 ? currentIndex - 1 : TAB_CONFIG.length - 1;
    }

    // Update Zustand store — we need to set activeTab there
    // For now we use a local state approach, but in Phase 2 this should use the store
    // We'll dispatch the tab change via the store
    useAppStore.setState({ activeTab: TAB_CONFIG[nextIndex].id as SidebarTab });

    // Focus the new tab button
    const tabButtons = tablistRef.current?.querySelectorAll('[role="tab"]');
    if (tabButtons && tabButtons[nextIndex]) {
      (tabButtons[nextIndex] as HTMLElement).focus();
    }
  }, [activeTab]);

  return (
    <>
      {/* Sidebar toggle button (visible when sidebar is closed) */}
      {!isSidebarOpen && (
        <button
          onClick={toggleSidebar}
          className={cn(
            'fixed right-0 top-1/2 -translate-y-1/2 z-[var(--z-sidebar)]',
            'bg-[hsl(var(--surface-glass))] backdrop-blur-xl',
            'border border-[hsl(var(--surface-glass-border))] border-r-0',
            'rounded-l-lg px-2 py-3',
            'text-[hsl(var(--neutral-400))] hover:text-[hsl(var(--neutral-100))]',
            'transition-all duration-[var(--duration-default)] ease-[var(--ease-spring)]',
            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[hsl(var(--brand-500))]',
          )}
          aria-label="Open sidebar"
        >
          <PanelRightOpen className="w-4 h-4" strokeWidth={1.5} />
        </button>
      )}

      {/* Sidebar panel */}
      <aside
        className={cn(
          'h-full w-80 shrink-0 flex flex-col',
          'border-l border-[hsl(var(--surface-glass-border))]',
          'bg-[hsl(var(--surface-sunken))] backdrop-blur-2xl',
          'z-[var(--z-sidebar)]',
          'transition-all duration-[var(--duration-default)] ease-[var(--ease-drawer)]',
          !isSidebarOpen && 'w-0 overflow-hidden border-l-0',
        )}
      >
        {/* Tab bar */}
        <div
          ref={tablistRef}
          role="tablist"
          onKeyDown={handleTablistKeyDown}
          aria-label="Sidebar navigation"
          className={cn(
            'flex shrink-0 border-b border-[hsl(var(--surface-glass-border))]',
            'bg-[hsl(var(--surface-glass))] backdrop-blur-md',
          )}
        >
          {TAB_CONFIG.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;

            return (
              <button
                key={tab.id}
                id={`tab-${tab.id}`}
                role="tab"
                aria-selected={isActive}
                aria-controls={`panel-${tab.id}`}
                tabIndex={isActive ? 0 : -1}
                onClick={() => useAppStore.setState({ activeTab: tab.id as SidebarTab })}
                className={cn(
                  'flex-1 min-w-[56px] py-3 flex flex-col items-center gap-1 transition-all duration-[var(--duration-default)]',
                  isActive
                    ? 'text-[hsl(var(--brand-500))] border-b-2 border-[hsl(var(--brand-500))] bg-[hsl(var(--brand-500)/0.05)]'
                    : 'text-[hsl(var(--neutral-400))] hover:text-[hsl(var(--neutral-100))] hover:bg-[hsl(var(--neutral-800)/0.3)]',
                  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[hsl(var(--brand-500))]',
                )}
                title={tab.label}
              >
                <Icon className="w-4 h-4" strokeWidth={1.5} />
                <span className="text-[10px] font-medium tracking-wide">{tab.label}</span>
              </button>
            );
          })}

          {/* Close sidebar button */}
          <button
            onClick={toggleSidebar}
            className={cn(
              'px-3 text-[hsl(var(--neutral-400))] hover:text-[hsl(var(--neutral-100))]',
              'transition-colors duration-[var(--duration-default)]',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[hsl(var(--brand-500))]',
            )}
            aria-label="Close sidebar"
          >
            <PanelRightClose className="w-4 h-4" strokeWidth={1.5} />
          </button>
        </div>

        {/* CRITICAL: All panels rendered in DOM, visibility controlled via CSS.
            Never use conditional rendering (ternary/null) — it destroys SSE streams. */}
        <div className="flex-1 overflow-hidden">
          {/* Chat Panel — active when 'chat' */}
          <div
            role="tabpanel"
            id="panel-chat"
            aria-labelledby="tab-chat"
            className={cn(
              'h-full flex flex-col',
              activeTab === 'chat' ? 'flex' : 'hidden',
            )}
          >
            <ChatPanel />
          </div>

          {/* DLQ Panel — active when 'dlq' */}
          <div
            role="tabpanel"
            id="panel-dlq"
            aria-labelledby="tab-dlq"
            className={cn(
              'h-full flex flex-col overflow-y-auto',
              activeTab === 'dlq' ? 'flex' : 'hidden',
            )}
          >
            <DLQPanel />
          </div>

          {/* Quota Panel — active when 'quota' */}
          <div
            role="tabpanel"
            id="panel-quota"
            aria-labelledby="tab-quota"
            className={cn(
              'h-full flex flex-col overflow-y-auto',
              activeTab === 'quota' ? 'flex' : 'hidden',
            )}
          >
            <QuotaPanel />
          </div>

          {/* YouTube Panel — active when 'youtube' */}
          <div
            role="tabpanel"
            id="panel-youtube"
            aria-labelledby="tab-youtube"
            className={cn(
              'h-full flex flex-col',
              activeTab === 'youtube' ? 'flex' : 'hidden',
            )}
          >
            <YouTubePanel />
          </div>

          {/* Settings Panel — active when 'settings' */}
          <div
            role="tabpanel"
            id="panel-settings"
            aria-labelledby="tab-settings"
            className={cn(
              'h-full flex flex-col overflow-y-auto',
              activeTab === 'settings' ? 'flex' : 'hidden',
            )}
          >
            <ModelRegistry />
            <SkillViewer />
            <KnowledgeBase />
          </div>
        </div>
      </aside>
    </>
  );
}
