'use client'

import { useCallback, useEffect, useState } from 'react'
import { useHotkeys } from 'react-hotkeys-hook'
import { useUIStore } from '@/stores'

type ShortcutHandler = () => void

interface KeyboardShortcut {
  key: string
  description: string
  handler: ShortcutHandler
  enabled?: boolean
}

const defaultShortcuts: KeyboardShortcut[] = [
  {
    key: 'mod+k',
    description: 'Open command palette',
    handler: () => {},
  },
  {
    key: 'mod+/',
    description: 'Toggle help',
    handler: () => {},
  },
  {
    key: 'mod+b',
    description: 'Toggle sidebar',
    handler: () => {},
  },
  {
    key: 'mod+,',
    description: 'Open settings',
    handler: () => {},
  },
  {
    key: 'escape',
    description: 'Close modal/menu',
    handler: () => {},
  },
]

export function useKeyboardShortcuts() {
  const {
    toggleCommandPalette,
    toggleSidebar,
    toggleSettings,
    toggleHelp,
    commandPaletteOpen,
    settingsOpen,
    helpOpen,
    setCommandPaletteOpen,
    setSettingsOpen,
    setHelpOpen,
  } = useUIStore()

  // Command palette: Cmd+K / Ctrl+K
  useHotkeys('mod+k', (e) => {
    e.preventDefault()
    toggleCommandPalette()
  }, {
    enableOnFormTags: false,
  })

  // Help: Cmd+/ / Ctrl+/
  useHotkeys('mod+/', (e) => {
    e.preventDefault()
    toggleHelp()
  }, {
    enableOnFormTags: false,
  })

  // Sidebar toggle: Cmd+B / Ctrl+B
  useHotkeys('mod+b', (e) => {
    e.preventDefault()
    toggleSidebar()
  }, {
    enableOnFormTags: false,
  })

  // Settings: Cmd+, / Ctrl+,
  useHotkeys('mod+,', (e) => {
    e.preventDefault()
    toggleSettings()
  }, {
    enableOnFormTags: false,
  })

  // Escape to close modals
  useHotkeys('escape', (e) => {
    if (commandPaletteOpen) {
      e.preventDefault()
      setCommandPaletteOpen(false)
    } else if (settingsOpen) {
      e.preventDefault()
      setSettingsOpen(false)
    } else if (helpOpen) {
      e.preventDefault()
      setHelpOpen(false)
    }
  }, {
    enableOnFormTags: true,
  })

  return {
    shortcuts: defaultShortcuts,
  }
}

// Hook for list navigation (j/k keys)
export function useListNavigation(
  itemCount: number,
  onSelect?: (index: number) => void,
  options?: {
    enabled?: boolean
    loop?: boolean
  }
) {
  const { enabled = true, loop = true } = options || {}
  const [activeIndex, setActiveIndex] = useState(0)

  useHotkeys('j', () => {
    if (!enabled) return
    setActiveIndex((prev) => {
      const next = prev + 1
      if (next >= itemCount) {
        return loop ? 0 : prev
      }
      return next
    })
  }, {
    enableOnFormTags: false,
    enabled,
  })

  useHotkeys('k', () => {
    if (!enabled) return
    setActiveIndex((prev) => {
      const next = prev - 1
      if (next < 0) {
        return loop ? itemCount - 1 : 0
      }
      return next
    })
  }, {
    enableOnFormTags: false,
    enabled,
  })

  useHotkeys('enter', () => {
    if (!enabled) return
    onSelect?.(activeIndex)
  }, {
    enableOnFormTags: false,
    enabled,
  })

  return {
    activeIndex,
    setActiveIndex,
  }
}

