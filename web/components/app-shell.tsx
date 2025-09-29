"use client"

import { type ReactNode, useState } from "react"
import Link from "next/link"
import { Menu, X, User } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"

interface AppShellProps {
  children: ReactNode
  leftRail?: ReactNode
  showLeftRail?: boolean
}

export function AppShell({ children, leftRail, showLeftRail = false }: AppShellProps) {
  const [isLeftRailOpen, setIsLeftRailOpen] = useState(showLeftRail)

  return (
    <div className="min-h-screen flex flex-col bg-background">
      {/* Header */}
      <header className="sticky top-0 z-50 w-full border-b border-border-color bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="container flex h-16 items-center justify-between px-4 md:px-6">
          <div className="flex items-center gap-4">
            {showLeftRail && (
              <Button
                variant="ghost"
                size="icon"
                className="md:hidden"
                onClick={() => setIsLeftRailOpen(!isLeftRailOpen)}
              >
                {isLeftRailOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
              </Button>
            )}
            <Link href="/" className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-full bg-accent flex items-center justify-center">
                <svg viewBox="0 0 24 24" fill="none" className="w-5 h-5 text-white" xmlns="http://www.w3.org/2000/svg">
                  <circle cx="12" cy="12" r="4" stroke="currentColor" strokeWidth="2" />
                  <circle cx="12" cy="12" r="8" stroke="currentColor" strokeWidth="1.5" opacity="0.5" />
                </svg>
              </div>
              <span className="font-semibold text-lg text-foreground">Iris Research</span>
            </Link>
          </div>

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" className="rounded-full">
                <User className="h-5 w-5" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-48">
              <DropdownMenuItem>Profile</DropdownMenuItem>
              <DropdownMenuItem>Settings</DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem>Sign out</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </header>

      {/* Main content */}
      <div className="flex-1 flex">
        {/* Left rail - collapsible on mobile */}
        {showLeftRail && leftRail && (
          <>
            {/* Mobile overlay */}
            {isLeftRailOpen && (
              <div className="fixed inset-0 bg-foreground/20 z-40 md:hidden" onClick={() => setIsLeftRailOpen(false)} />
            )}

            {/* Left rail content */}
            <aside
              className={`
                fixed md:sticky top-16 left-0 z-40 h-[calc(100vh-4rem)]
                w-80 border-r border-border-color bg-background
                transition-transform duration-200 ease-in-out
                ${isLeftRailOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0"}
              `}
            >
              {leftRail}
            </aside>
          </>
        )}

        {/* Main content area */}
        <main className="flex-1 overflow-auto">{children}</main>
      </div>
    </div>
  )
}
