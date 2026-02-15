import { SkeletonCard } from '@/components/ui/skeletons'
import { Skeleton } from '@/components/ui/skeleton'

export default function TemplatesLoading() {
  return (
    <div className="min-h-screen flex flex-col">
      {/* Header skeleton */}
      <div className="sticky top-0 z-50 w-full border-b border-border bg-background h-16" />

      <main className="flex-1 w-full max-w-6xl mx-auto px-4 md:px-6 py-12 space-y-10">
        {/* Title skeleton */}
        <div className="text-center space-y-3">
          <Skeleton className="h-12 w-80 mx-auto" />
          <Skeleton className="h-5 w-96 mx-auto" />
        </div>

        {/* Tabs skeleton */}
        <div className="flex gap-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-9 w-20 rounded-lg" />
          ))}
        </div>

        {/* Search skeleton */}
        <Skeleton className="h-9 w-full rounded-2xl" />

        {/* Grid skeleton */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <SkeletonCard key={i} hasActions />
          ))}
        </div>
      </main>
    </div>
  )
}
