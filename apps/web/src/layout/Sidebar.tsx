import { useState, useCallback, useRef } from 'react';
import { QuotaPanel } from '../components/telemetry/QuotaPanel';
import { ModelRegistry } from '../components/telemetry/ModelRegistry';
import { SkillViewer } from '../components/system/SkillViewer';
import { KnowledgeBase } from '../components/system/KnowledgeBase';
import { ChatPanel } from '../components/chat/ChatPanel';
import { YouTubePanel } from '../components/youtube/YouTubePanel';

type SidebarTab = 'chat' | 'youtube' | 'quota' | 'models' | 'skills' | 'knowledge';

export function Sidebar() {
  const [activeTab, setActiveTab] = useState<SidebarTab>('chat');
  const [isOpen, setIsOpen] = useState(() => {
    if (typeof window !== 'undefined') return window.innerWidth >= 1024;
    return true;
  });
  const tablistRef = useRef<HTMLDivElement>(null);

  const tabs: { id: SidebarTab; label: string; icon: string }[] = [
    { id: 'chat',      label: 'Chat',       icon: '💬' },
    { id: 'youtube',   label: 'YouTube',    icon: '📺' },
    { id: 'quota',     label: 'Quota',      icon: '📊' },
    { id: 'models',    label: 'Models',     icon: '🤖' },
    { id: 'skills',    label: 'Skills',     icon: '📝' },
    { id: 'knowledge', label: 'KB',         icon: '📚' },
  ];

  // Arrow key navigation for tabs
  const handleTablistKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;

    const currentIndex = tabs.findIndex((t) => t.id === activeTab);
    let nextIndex: number;

    if (e.key === 'ArrowRight') {
      nextIndex = currentIndex < tabs.length - 1 ? currentIndex + 1 : 0;
    } else {
      nextIndex = currentIndex > 0 ? currentIndex - 1 : tabs.length - 1;
    }

    setActiveTab(tabs[nextIndex].id);

    // Focus the new tab button
    const tabButtons = tablistRef.current?.querySelectorAll('[role="tab"]');
    if (tabButtons && tabButtons[nextIndex] instanceof HTMLElement) {
      tabButtons[nextIndex].focus();
    }
  }, [activeTab, tabs]);

  return (
    <>
      {/* Toggle button */}
      {!isOpen && (
        <button
          onClick={() => setIsOpen(true)}
          className="fixed right-0 top-1/2 -translate-y-1/2 bg-gray-800 border border-gray-700 border-r-0 rounded-l-lg px-2 py-4 text-gray-400 hover:text-white z-30"
        >
          ◀
        </button>
      )}

      <aside
        className={`
          ${isOpen ? 'w-96' : 'w-0'}
          transition-all duration-300 overflow-hidden
          bg-gray-900 border-l border-gray-800 shrink-0 flex flex-col
        `}
      >
        {/* Tab bar */}
        <div
          ref={tablistRef}
          role="tablist"
          onKeyDown={handleTablistKeyDown}
          className="flex flex-wrap border-b border-gray-800 shrink-0"
        >
          {tabs.map((tab) => (
            <button
              key={tab.id}
              id={`tab-${tab.id}`}
              role="tab"
              aria-selected={activeTab === tab.id}
              aria-controls={`panel-${tab.id}`}
              tabIndex={activeTab === tab.id ? 0 : -1}
              onClick={() => setActiveTab(tab.id)}
              className={`flex-1 min-w-[60px] py-2 text-xs font-medium ${
                activeTab === tab.id
                  ? 'text-white border-b-2 border-blue-500'
                  : 'text-gray-500 hover:text-gray-300'
              }`}
              title={tab.label}
            >
              {tab.icon}
            </button>
          ))}
          <button
            onClick={() => setIsOpen(false)}
            className="px-3 text-gray-500 hover:text-white"
          >
            ▶
          </button>
        </div>

        {/* Tab content */}
        <div
          role="tabpanel"
          id={`panel-${activeTab}`}
          aria-labelledby={`tab-${activeTab}`}
          className="flex-1 overflow-hidden flex flex-col"
        >
          {activeTab === 'chat' && <ChatPanel />}
          {activeTab === 'youtube' && <YouTubePanel />}
          {activeTab === 'quota' && (
            <div className="overflow-y-auto scrollbar-thin"><QuotaPanel /></div>
          )}
          {activeTab === 'models' && (
            <div className="overflow-y-auto scrollbar-thin"><ModelRegistry /></div>
          )}
          {activeTab === 'skills' && (
            <div className="overflow-y-auto scrollbar-thin"><SkillViewer /></div>
          )}
          {activeTab === 'knowledge' && (
            <div className="overflow-y-auto scrollbar-thin"><KnowledgeBase /></div>
          )}
        </div>
      </aside>
    </>
  );
}
