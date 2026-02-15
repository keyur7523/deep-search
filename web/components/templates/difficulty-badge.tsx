import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

const difficultyConfig = {
  beginner: {
    label: 'Beginner',
    className: 'bg-green-100 text-green-700 border-green-200 dark:bg-green-900/30 dark:text-green-400 dark:border-green-800',
  },
  intermediate: {
    label: 'Intermediate',
    className: 'bg-amber-100 text-amber-700 border-amber-200 dark:bg-amber-900/30 dark:text-amber-400 dark:border-amber-800',
  },
  advanced: {
    label: 'Advanced',
    className: 'bg-red-100 text-red-700 border-red-200 dark:bg-red-900/30 dark:text-red-400 dark:border-red-800',
  },
} as const

interface DifficultyBadgeProps {
  difficulty: 'beginner' | 'intermediate' | 'advanced'
  className?: string
}

export function DifficultyBadge({ difficulty, className }: DifficultyBadgeProps) {
  const config = difficultyConfig[difficulty]
  return (
    <Badge variant="outline" className={cn(config.className, className)}>
      {config.label}
    </Badge>
  )
}
