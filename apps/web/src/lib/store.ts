// apps/web/src/lib/store.ts
// Zustand V5 Global Application Store
//
// We minimize React Context usage — all global UI state lives here.
// Cards are NOT stored here; they are fetched via SWR + Supabase Realtime.
//
// CRITICAL (Zustand V5):
// The extra `()` after `create<AppState>` is required by V5's curried pattern.
// Omitting it causes a runtime TypeError.
//
// CRITICAL (SSR safety):
// `window.innerWidth` is guarded with `typeof window !== 'undefined'`
// to prevent SSR/build-time crashes.

import { create } from 'zustand';

type SidebarTab = 'chat' | 'dlq' | 'quota' | 'youtube' | 'settings';

interface AppState {
  // Global search — consumed by Kanban board filter
  searchQuery: string;
  setSearchQuery: (q: string) => void;

  // Active card for the drawer (Phase 4)
  activeDrawerCardId: string | null;
  setActiveDrawerCardId: (id: string | null) => void;

  // Sidebar state
  isSidebarOpen: boolean;
  toggleSidebar: () => void;
  activeTab: SidebarTab;
}

export type { SidebarTab };

export const useAppStore = create<AppState>()((set) => ({
  searchQuery: '',
  setSearchQuery: (q) => set({ searchQuery: q }),

  activeDrawerCardId: null,
  setActiveDrawerCardId: (id) => set({ activeDrawerCardId: id }),

  isSidebarOpen: typeof window !== 'undefined' ? window.innerWidth >= 1024 : true,
  toggleSidebar: () => set((state) => ({ isSidebarOpen: !state.isSidebarOpen })),

  activeTab: 'chat',
}));
