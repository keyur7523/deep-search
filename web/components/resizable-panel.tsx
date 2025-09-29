"use client"

import { type ReactNode, useRef, useState, useEffect } from "react"
import { cn } from "@/lib/utils"

interface ResizablePanelProps {
  children: ReactNode
  defaultWidth: number
  minWidth: number
  maxWidth: number
  onResize?: (width: number) => void
  className?: string
}

export function ResizablePanel({
  children,
  defaultWidth,
  minWidth,
  maxWidth,
  onResize,
  className,
}: ResizablePanelProps) {
  const [width, setWidth] = useState(defaultWidth)
  const [isResizing, setIsResizing] = useState(false)
  const panelRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isResizing) return

      const newWidth = e.clientX
      const clampedWidth = Math.max(minWidth, Math.min(maxWidth, newWidth))
      setWidth(clampedWidth)
      onResize?.(clampedWidth)
    }

    const handleMouseUp = () => {
      setIsResizing(false)
    }

    if (isResizing) {
      document.addEventListener("mousemove", handleMouseMove)
      document.addEventListener("mouseup", handleMouseUp)
      document.body.style.cursor = "col-resize"
      document.body.style.userSelect = "none"
    }

    return () => {
      document.removeEventListener("mousemove", handleMouseMove)
      document.removeEventListener("mouseup", handleMouseUp)
      document.body.style.cursor = ""
      document.body.style.userSelect = ""
    }
  }, [isResizing, minWidth, maxWidth, onResize])

  return (
    <div ref={panelRef} style={{ width }} className={cn("relative shrink-0", className)}>
      {children}

      {/* Resize handle */}
      <div
        className="absolute top-0 right-0 w-1 h-full cursor-col-resize hover:bg-[#6d28d9] transition-colors group"
        onMouseDown={() => setIsResizing(true)}
      >
        <div className="absolute inset-y-0 -left-1 -right-1" />
      </div>
    </div>
  )
}
