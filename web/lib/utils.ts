import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatDate(date: Date): string {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date)
}

export function getStatusColor(status: string): string {
  const colors: Record<string, string> = {
    queued: "bg-muted text-muted-foreground",
    searching: "bg-blue-100 text-blue-700",
    reflecting: "bg-purple-100 text-purple-700",
    drafting: "bg-amber-100 text-amber-700",
    done: "bg-green-100 text-green-700",
    "needs review": "bg-red-100 text-red-700",
  }
  return colors[status.toLowerCase()] || colors.queued
}
