'use client'

import { useKeyboardShortcuts } from '@/hooks/useKeyboardShortcuts'
import { CommandPalette } from './command-palette'
import { KeyboardShortcutsDialog } from './keyboard-shortcuts-dialog'

export function GlobalUI() {
  // Initialize global keyboard shortcuts
  useKeyboardShortcuts()

  return (
    <>
      <CommandPalette />
      <KeyboardShortcutsDialog />
    </>
  )
}
