'use client'

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { useUIStore } from '@/stores'
import { motion } from 'framer-motion'

interface ShortcutSection {
  title: string
  shortcuts: {
    keys: string[]
    description: string
  }[]
}

const shortcutSections: ShortcutSection[] = [
  {
    title: 'General',
    shortcuts: [
      { keys: ['⌘', 'K'], description: 'Open command palette' },
      { keys: ['⌘', '/'], description: 'Show keyboard shortcuts' },
      { keys: ['⌘', 'B'], description: 'Toggle sidebar' },
      { keys: ['⌘', ','], description: 'Open settings' },
      { keys: ['Esc'], description: 'Close modal or menu' },
    ],
  },
  {
    title: 'Navigation',
    shortcuts: [
      { keys: ['G', 'H'], description: 'Go to home' },
      { keys: ['J'], description: 'Move down in list' },
      { keys: ['K'], description: 'Move up in list' },
      { keys: ['Enter'], description: 'Select item' },
    ],
  },
  {
    title: 'Research',
    shortcuts: [
      { keys: ['N'], description: 'New research' },
      { keys: ['⌘', 'Enter'], description: 'Start research' },
      { keys: ['⌘', 'S'], description: 'Save/export report' },
    ],
  },
  {
    title: 'Theme',
    shortcuts: [
      { keys: ['⌘', 'Shift', 'L'], description: 'Light mode' },
      { keys: ['⌘', 'Shift', 'D'], description: 'Dark mode' },
    ],
  },
]

export function KeyboardShortcutsDialog() {
  const { helpOpen, setHelpOpen } = useUIStore()

  return (
    <Dialog open={helpOpen} onOpenChange={setHelpOpen}>
      <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Keyboard Shortcuts</DialogTitle>
          <DialogDescription>
            Use these shortcuts to navigate and perform actions quickly.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-6 py-4">
          {shortcutSections.map((section, sectionIndex) => (
            <motion.div
              key={section.title}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: sectionIndex * 0.05 }}
            >
              <h3 className="font-medium text-sm text-muted-foreground mb-3">
                {section.title}
              </h3>
              <div className="space-y-2">
                {section.shortcuts.map((shortcut, index) => (
                  <div
                    key={index}
                    className="flex items-center justify-between py-2 px-3 rounded-md hover:bg-muted/50 transition-colors"
                  >
                    <span className="text-sm">{shortcut.description}</span>
                    <div className="flex gap-1">
                      {shortcut.keys.map((key, keyIndex) => (
                        <kbd
                          key={keyIndex}
                          className="inline-flex h-6 min-w-6 items-center justify-center rounded border bg-muted px-1.5 font-mono text-xs font-medium"
                        >
                          {key}
                        </kbd>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </motion.div>
          ))}
        </div>

        <div className="border-t pt-4">
          <p className="text-xs text-muted-foreground text-center">
            Press <kbd className="px-1 py-0.5 rounded border bg-muted font-mono text-xs">⌘ K</kbd> to open the command palette for more actions
          </p>
        </div>
      </DialogContent>
    </Dialog>
  )
}
