import { create } from 'zustand'

interface UIState {
  // Sidebar state
  sidebarOpen: boolean
  sidebarWidth: number

  // Modal states
  commandPaletteOpen: boolean
  settingsOpen: boolean
  helpOpen: boolean

  // Loading states
  isNavigating: boolean
  globalLoading: boolean

  // Toast/notification queue
  notifications: Notification[]

  // Actions
  toggleSidebar: () => void
  setSidebarOpen: (open: boolean) => void
  setSidebarWidth: (width: number) => void

  toggleCommandPalette: () => void
  setCommandPaletteOpen: (open: boolean) => void

  toggleSettings: () => void
  setSettingsOpen: (open: boolean) => void

  toggleHelp: () => void
  setHelpOpen: (open: boolean) => void

  setNavigating: (navigating: boolean) => void
  setGlobalLoading: (loading: boolean) => void

  addNotification: (notification: Omit<Notification, 'id'>) => void
  removeNotification: (id: string) => void
  clearNotifications: () => void
}

interface Notification {
  id: string
  type: 'success' | 'error' | 'warning' | 'info'
  title: string
  message?: string
  duration?: number
}

export const useUIStore = create<UIState>()((set) => ({
  // Initial states
  sidebarOpen: true,
  sidebarWidth: 320,
  commandPaletteOpen: false,
  settingsOpen: false,
  helpOpen: false,
  isNavigating: false,
  globalLoading: false,
  notifications: [],

  // Sidebar actions
  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
  setSidebarOpen: (open) => set({ sidebarOpen: open }),
  setSidebarWidth: (width) => set({ sidebarWidth: Math.max(240, Math.min(480, width)) }),

  // Command palette actions
  toggleCommandPalette: () => set((state) => ({ commandPaletteOpen: !state.commandPaletteOpen })),
  setCommandPaletteOpen: (open) => set({ commandPaletteOpen: open }),

  // Settings actions
  toggleSettings: () => set((state) => ({ settingsOpen: !state.settingsOpen })),
  setSettingsOpen: (open) => set({ settingsOpen: open }),

  // Help actions
  toggleHelp: () => set((state) => ({ helpOpen: !state.helpOpen })),
  setHelpOpen: (open) => set({ helpOpen: open }),

  // Loading actions
  setNavigating: (navigating) => set({ isNavigating: navigating }),
  setGlobalLoading: (loading) => set({ globalLoading: loading }),

  // Notification actions
  addNotification: (notification) => set((state) => ({
    notifications: [
      ...state.notifications,
      { ...notification, id: crypto.randomUUID() }
    ]
  })),
  removeNotification: (id) => set((state) => ({
    notifications: state.notifications.filter((n) => n.id !== id)
  })),
  clearNotifications: () => set({ notifications: [] }),
}))
