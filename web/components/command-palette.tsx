'use client'

import { useEffect, useState, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from '@/components/ui/command'
import {
  Search,
  FileText,
  Settings,
  Moon,
  Sun,
  Monitor,
  HelpCircle,
  Home,
  Plus,
  History,
  Keyboard,
} from 'lucide-react'
import { useTheme } from 'next-themes'
import { useUIStore } from '@/stores'

interface CommandItem {
  id: string
  label: string
  icon: React.ReactNode
  shortcut?: string[]
  onSelect: () => void
  group: 'navigation' | 'actions' | 'theme' | 'help'
}

export function CommandPalette() {
  const router = useRouter()
  const { theme, setTheme } = useTheme()
  const {
    commandPaletteOpen,
    setCommandPaletteOpen,
    toggleSettings,
    toggleHelp,
  } = useUIStore()

  const commands: CommandItem[] = [
    // Navigation
    {
      id: 'home',
      label: 'Go to Home',
      icon: <Home className="mr-2 h-4 w-4" />,
      shortcut: ['G', 'H'],
      onSelect: () => {
        router.push('/')
        setCommandPaletteOpen(false)
      },
      group: 'navigation',
    },
    {
      id: 'new-research',
      label: 'New Research',
      icon: <Plus className="mr-2 h-4 w-4" />,
      shortcut: ['N'],
      onSelect: () => {
        router.push('/')
        setCommandPaletteOpen(false)
      },
      group: 'navigation',
    },
    {
      id: 'history',
      label: 'View History',
      icon: <History className="mr-2 h-4 w-4" />,
      onSelect: () => {
        // TODO: Navigate to history
        setCommandPaletteOpen(false)
      },
      group: 'navigation',
    },
    // Actions
    {
      id: 'settings',
      label: 'Open Settings',
      icon: <Settings className="mr-2 h-4 w-4" />,
      shortcut: ['⌘', ','],
      onSelect: () => {
        toggleSettings()
        setCommandPaletteOpen(false)
      },
      group: 'actions',
    },
    // Theme
    {
      id: 'theme-light',
      label: 'Light Mode',
      icon: <Sun className="mr-2 h-4 w-4" />,
      onSelect: () => {
        setTheme('light')
        setCommandPaletteOpen(false)
      },
      group: 'theme',
    },
    {
      id: 'theme-dark',
      label: 'Dark Mode',
      icon: <Moon className="mr-2 h-4 w-4" />,
      onSelect: () => {
        setTheme('dark')
        setCommandPaletteOpen(false)
      },
      group: 'theme',
    },
    {
      id: 'theme-system',
      label: 'System Theme',
      icon: <Monitor className="mr-2 h-4 w-4" />,
      onSelect: () => {
        setTheme('system')
        setCommandPaletteOpen(false)
      },
      group: 'theme',
    },
    // Help
    {
      id: 'help',
      label: 'Help & Documentation',
      icon: <HelpCircle className="mr-2 h-4 w-4" />,
      shortcut: ['⌘', '/'],
      onSelect: () => {
        toggleHelp()
        setCommandPaletteOpen(false)
      },
      group: 'help',
    },
    {
      id: 'shortcuts',
      label: 'Keyboard Shortcuts',
      icon: <Keyboard className="mr-2 h-4 w-4" />,
      shortcut: ['?'],
      onSelect: () => {
        toggleHelp()
        setCommandPaletteOpen(false)
      },
      group: 'help',
    },
  ]

  const navigationCommands = commands.filter((c) => c.group === 'navigation')
  const actionCommands = commands.filter((c) => c.group === 'actions')
  const themeCommands = commands.filter((c) => c.group === 'theme')
  const helpCommands = commands.filter((c) => c.group === 'help')

  return (
    <CommandDialog open={commandPaletteOpen} onOpenChange={setCommandPaletteOpen}>
      <CommandInput placeholder="Type a command or search..." />
      <CommandList>
        <CommandEmpty>No results found.</CommandEmpty>

        <CommandGroup heading="Navigation">
          {navigationCommands.map((command) => (
            <CommandItem
              key={command.id}
              onSelect={command.onSelect}
              className="flex items-center justify-between"
            >
              <div className="flex items-center">
                {command.icon}
                <span>{command.label}</span>
              </div>
              {command.shortcut && (
                <div className="flex gap-1">
                  {command.shortcut.map((key, i) => (
                    <kbd
                      key={i}
                      className="pointer-events-none h-5 select-none items-center gap-1 rounded border bg-muted px-1.5 font-mono text-[10px] font-medium opacity-100 inline-flex"
                    >
                      {key}
                    </kbd>
                  ))}
                </div>
              )}
            </CommandItem>
          ))}
        </CommandGroup>

        <CommandSeparator />

        <CommandGroup heading="Actions">
          {actionCommands.map((command) => (
            <CommandItem
              key={command.id}
              onSelect={command.onSelect}
              className="flex items-center justify-between"
            >
              <div className="flex items-center">
                {command.icon}
                <span>{command.label}</span>
              </div>
              {command.shortcut && (
                <div className="flex gap-1">
                  {command.shortcut.map((key, i) => (
                    <kbd
                      key={i}
                      className="pointer-events-none h-5 select-none items-center gap-1 rounded border bg-muted px-1.5 font-mono text-[10px] font-medium opacity-100 inline-flex"
                    >
                      {key}
                    </kbd>
                  ))}
                </div>
              )}
            </CommandItem>
          ))}
        </CommandGroup>

        <CommandSeparator />

        <CommandGroup heading="Theme">
          {themeCommands.map((command) => (
            <CommandItem
              key={command.id}
              onSelect={command.onSelect}
              className="flex items-center"
            >
              {command.icon}
              <span>{command.label}</span>
              {theme === command.id.replace('theme-', '') && (
                <span className="ml-auto text-xs text-muted-foreground">Active</span>
              )}
            </CommandItem>
          ))}
        </CommandGroup>

        <CommandSeparator />

        <CommandGroup heading="Help">
          {helpCommands.map((command) => (
            <CommandItem
              key={command.id}
              onSelect={command.onSelect}
              className="flex items-center justify-between"
            >
              <div className="flex items-center">
                {command.icon}
                <span>{command.label}</span>
              </div>
              {command.shortcut && (
                <div className="flex gap-1">
                  {command.shortcut.map((key, i) => (
                    <kbd
                      key={i}
                      className="pointer-events-none h-5 select-none items-center gap-1 rounded border bg-muted px-1.5 font-mono text-[10px] font-medium opacity-100 inline-flex"
                    >
                      {key}
                    </kbd>
                  ))}
                </div>
              )}
            </CommandItem>
          ))}
        </CommandGroup>
      </CommandList>
    </CommandDialog>
  )
}
