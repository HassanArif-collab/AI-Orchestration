import { useState } from 'react';
import { QuotaPanel } from '../components/telemetry/QuotaPanel';
import { ModelRegistry } from '../components/telemetry/ModelRegistry';
import { SkillViewer } from '../components/system/SkillViewer';

type SidebarTab = 'quota' | 'models' | 'skills';

export function Sidebar() {
  const [activeTab, setActiveTab] = useState<SidebarTab>('quota');
  const [isOpen, setIsOpen] = useState(false);

  const tabs: { id: SidebarTab; label: string; icon: string }[] = [
    { id: 'quota',  label: 'Live Quota',   icon: '📊' },
    { id: 'models', label: 'Model Map',    icon: '🤖' },
    { id: 'skills', label: 'System',       icon: '⚙️' },
  ];

  return (
    <>
      {/* Toggle button (visible when sidebar is closed) */}
      {!isOpen && (
        <button
          onClick={() => setIsOpen(true)}
          className="fixed right-0 top-1/2 -translate-y-1/2 bg-gray-800 border border-gray-700 border-r-0 rounded-l-lg px-2 py-4 text-gray-400 hover:text-white z-30"
        >
          ◀
        </button>
      )}

      {/* Sidebar panel */}
      <aside
        className={`
          ${isOpen ? 'w-80' : 'w-0'}
          transition-all duration-300 overflow-hidden
          bg-gray-900 border-l border-gray-800 shrink-0 flex flex-col
        `}
      >
        {/* Tab bar */}
        <div className="flex border-b border-gray-800 shrink-0">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex-1 py-2 text-xs font-medium ${
                activeTab === tab.id
                  ? 'text-white border-b-2 border-blue-500'
                  : 'text-gray-500 hover:text-gray-300'
              }`}
            >
              {tab.icon} {tab.label}
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
        <div className="flex-1 overflow-y-auto scrollbar-thin">
          {activeTab === 'quota' && <QuotaPanel />}
          {activeTab === 'models' && <ModelRegistry />}
          {activeTab === 'skills' && <SkillViewer />}
        </div>
      </aside>
    </>
  );
}
