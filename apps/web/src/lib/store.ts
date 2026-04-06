// apps/web/src/lib/store.ts
// Zustand V5 Global Application Store
//
// We minimize React Context usage — all global UI state lives here.
// Cards are NOT stored here; they are fetched via SWR + Supabase Realtime.

import { create } from 'zustand';

interface AppState {
  searchQuery: string;
  setSearchQuery: (q: string) => void;
  activeDrawerCardId: string | null;
  setActiveDrawerCardId: (id: string | null) => void;
  isSidebarOpen: boolean;
  toggleSidebar: () => void;
}

export const useAppStore = create<AppState>()((set) => ({
  searchQuery: '',
  setSearchQuery: (q) => set({ searchQuery: q }),
  activeDrawerCardId: null,
  setActiveDrawerCardId: (id) => set({ activeDrawerCardId: id }),
  isSidebarOpen: typeof window !== 'undefined' ? window.innerWidth >= 1024 : true,
  toggleSidebar: () => set((state) => ({ isSidebarOpen: !state.isSidebarOpen })),
}));
