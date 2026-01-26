import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export type Theme = 'light' | 'dark' | 'system'

interface ThemeState {
  theme: Theme
  resolvedTheme: 'light' | 'dark'
  setTheme: (theme: Theme) => void
  setResolvedTheme: (resolved: 'light' | 'dark') => void
  toggleTheme: () => void
}

export const useThemeStore = create<ThemeState>()(
  persist(
    (set, get) => ({
      theme: 'system',
      resolvedTheme: 'light',

      setTheme: (theme) => set({ theme }),

      setResolvedTheme: (resolved) => set({ resolvedTheme: resolved }),

      toggleTheme: () => {
        const { theme } = get()
        const newTheme: Theme = theme === 'light' ? 'dark' : theme === 'dark' ? 'system' : 'light'
        set({ theme: newTheme })
      },
    }),
    {
      name: 'theme-storage',
      partialize: (state) => ({ theme: state.theme }),
    }
  )
)
