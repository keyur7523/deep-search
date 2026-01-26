'use client'

import { cn } from '@/lib/utils'
import { Skeleton } from './skeleton'

// ============= Base Skeleton Components =============

interface SkeletonTextProps {
  lines?: number
  className?: string
  lastLineWidth?: string
}

export function SkeletonText({ lines = 3, className, lastLineWidth = '60%' }: SkeletonTextProps) {
  return (
    <div className={cn('space-y-2', className)}>
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton
          key={i}
          className="h-4"
          style={{ width: i === lines - 1 ? lastLineWidth : '100%' }}
        />
      ))}
    </div>
  )
}

interface SkeletonHeadingProps {
  className?: string
  level?: 1 | 2 | 3
}

export function SkeletonHeading({ className, level = 2 }: SkeletonHeadingProps) {
  const heights = { 1: 'h-8', 2: 'h-6', 3: 'h-5' }
  const widths = { 1: 'w-3/4', 2: 'w-2/3', 3: 'w-1/2' }

  return (
    <Skeleton className={cn(heights[level], widths[level], className)} />
  )
}

interface SkeletonAvatarProps {
  size?: 'sm' | 'md' | 'lg'
  className?: string
}

export function SkeletonAvatar({ size = 'md', className }: SkeletonAvatarProps) {
  const sizes = { sm: 'h-8 w-8', md: 'h-10 w-10', lg: 'h-12 w-12' }

  return (
    <Skeleton className={cn('rounded-full', sizes[size], className)} />
  )
}

interface SkeletonButtonProps {
  size?: 'sm' | 'md' | 'lg'
  className?: string
}

export function SkeletonButton({ size = 'md', className }: SkeletonButtonProps) {
  const sizes = {
    sm: 'h-8 w-20',
    md: 'h-10 w-24',
    lg: 'h-12 w-32'
  }

  return (
    <Skeleton className={cn('rounded-md', sizes[size], className)} />
  )
}

interface SkeletonBadgeProps {
  className?: string
}

export function SkeletonBadge({ className }: SkeletonBadgeProps) {
  return (
    <Skeleton className={cn('h-5 w-16 rounded-full', className)} />
  )
}

// ============= Composite Skeleton Components =============

interface SkeletonCardProps {
  className?: string
  hasImage?: boolean
  hasActions?: boolean
}

export function SkeletonCard({ className, hasImage = false, hasActions = false }: SkeletonCardProps) {
  return (
    <div className={cn('rounded-lg border bg-card p-4 space-y-4', className)}>
      {hasImage && (
        <Skeleton className="h-40 w-full rounded-md" />
      )}
      <div className="space-y-2">
        <SkeletonHeading level={3} />
        <SkeletonText lines={2} />
      </div>
      {hasActions && (
        <div className="flex gap-2 pt-2">
          <SkeletonButton size="sm" />
          <SkeletonButton size="sm" />
        </div>
      )}
    </div>
  )
}

interface SkeletonTableProps {
  rows?: number
  columns?: number
  className?: string
}

export function SkeletonTable({ rows = 5, columns = 4, className }: SkeletonTableProps) {
  return (
    <div className={cn('w-full', className)}>
      {/* Header */}
      <div className="flex gap-4 pb-3 border-b">
        {Array.from({ length: columns }).map((_, i) => (
          <Skeleton key={i} className="h-4 flex-1" />
        ))}
      </div>
      {/* Rows */}
      <div className="divide-y">
        {Array.from({ length: rows }).map((_, rowIndex) => (
          <div key={rowIndex} className="flex gap-4 py-3">
            {Array.from({ length: columns }).map((_, colIndex) => (
              <Skeleton
                key={colIndex}
                className="h-4 flex-1"
                style={{ width: colIndex === 0 ? '40%' : undefined }}
              />
            ))}
          </div>
        ))}
      </div>
    </div>
  )
}

interface SkeletonListProps {
  items?: number
  hasIcon?: boolean
  hasSubtext?: boolean
  className?: string
}

export function SkeletonList({ items = 5, hasIcon = true, hasSubtext = false, className }: SkeletonListProps) {
  return (
    <div className={cn('space-y-3', className)}>
      {Array.from({ length: items }).map((_, i) => (
        <div key={i} className="flex items-start gap-3">
          {hasIcon && <SkeletonAvatar size="sm" />}
          <div className="flex-1 space-y-1.5">
            <Skeleton className="h-4 w-3/4" />
            {hasSubtext && <Skeleton className="h-3 w-1/2" />}
          </div>
        </div>
      ))}
    </div>
  )
}

// ============= Research-Specific Skeletons =============

export function SkeletonSourceCard({ className }: { className?: string }) {
  return (
    <div className={cn('rounded-lg border bg-card p-4 space-y-3', className)}>
      <div className="flex items-start justify-between">
        <div className="flex-1 space-y-2">
          <Skeleton className="h-5 w-4/5" />
          <Skeleton className="h-3 w-1/3" />
        </div>
        <SkeletonBadge />
      </div>
      <SkeletonText lines={2} />
      <div className="flex gap-2">
        <SkeletonBadge />
        <SkeletonBadge />
      </div>
    </div>
  )
}

export function SkeletonOutlineItem({ className }: { className?: string }) {
  return (
    <div className={cn('flex items-center gap-3 p-2', className)}>
      <Skeleton className="h-5 w-5 rounded" />
      <div className="flex-1 space-y-1">
        <Skeleton className="h-4 w-2/3" />
        <Skeleton className="h-3 w-1/2" />
      </div>
      <Skeleton className="h-4 w-8 rounded-full" />
    </div>
  )
}

export function SkeletonAgentEvent({ className }: { className?: string }) {
  return (
    <div className={cn('flex items-start gap-3 p-3 rounded-lg border', className)}>
      <Skeleton className="h-8 w-8 rounded-full shrink-0" />
      <div className="flex-1 space-y-2">
        <div className="flex items-center gap-2">
          <Skeleton className="h-4 w-24" />
          <Skeleton className="h-3 w-16" />
        </div>
        <SkeletonText lines={1} />
      </div>
    </div>
  )
}

export function SkeletonReport({ className }: { className?: string }) {
  return (
    <div className={cn('space-y-6', className)}>
      <SkeletonHeading level={1} />
      <SkeletonText lines={4} />

      <SkeletonHeading level={2} />
      <SkeletonText lines={3} />

      <SkeletonHeading level={2} />
      <SkeletonText lines={5} />

      <SkeletonHeading level={2} />
      <SkeletonText lines={4} />
    </div>
  )
}

export function SkeletonResearchSidebar({ className }: { className?: string }) {
  return (
    <div className={cn('space-y-6 p-4', className)}>
      {/* Progress section */}
      <div className="space-y-2">
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-2 w-full rounded-full" />
      </div>

      {/* Sources section */}
      <div className="space-y-3">
        <Skeleton className="h-5 w-20" />
        <SkeletonSourceCard />
        <SkeletonSourceCard />
        <SkeletonSourceCard />
      </div>

      {/* Outline section */}
      <div className="space-y-2">
        <Skeleton className="h-5 w-16" />
        <SkeletonOutlineItem />
        <SkeletonOutlineItem />
        <SkeletonOutlineItem />
      </div>
    </div>
  )
}

export function SkeletonTopicForm({ className }: { className?: string }) {
  return (
    <div className={cn('space-y-6 max-w-2xl mx-auto', className)}>
      <div className="text-center space-y-2">
        <Skeleton className="h-10 w-3/4 mx-auto" />
        <Skeleton className="h-4 w-1/2 mx-auto" />
      </div>

      <div className="space-y-4">
        <Skeleton className="h-12 w-full rounded-lg" />
        <Skeleton className="h-24 w-full rounded-lg" />
      </div>

      <div className="flex gap-4 justify-center">
        <SkeletonButton size="lg" />
        <SkeletonButton size="lg" />
      </div>
    </div>
  )
}
