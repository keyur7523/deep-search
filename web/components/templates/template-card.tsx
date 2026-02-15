import Link from 'next/link'
import Image from 'next/image'
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { DifficultyBadge } from './difficulty-badge'
import { Clock, FileText } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { ResearchTemplate } from '@/types/contentful'

interface TemplateCardProps {
  template: ResearchTemplate
  className?: string
}

export function TemplateCard({ template, className }: TemplateCardProps) {
  return (
    <Link href={`/templates/${template.slug}`} className="group block">
      <Card className={cn(
        'h-full transition-all duration-200 hover:shadow-md hover:-translate-y-0.5',
        className
      )}>
        <CardHeader>
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-center gap-3">
              {template.icon ? (
                <Image
                  src={template.icon.url}
                  alt={template.icon.alt}
                  width={40}
                  height={40}
                  className="rounded-lg"
                />
              ) : (
                <div className="w-10 h-10 rounded-lg bg-gradient-to-r from-purple-600 to-blue-600 flex items-center justify-center">
                  <FileText className="w-5 h-5 text-white" />
                </div>
              )}
              <CardTitle className="text-base group-hover:text-primary transition-colors">
                {template.title}
              </CardTitle>
            </div>
            <DifficultyBadge difficulty={template.difficulty} />
          </div>
          <CardDescription className="line-clamp-2 mt-2">
            {template.promptText.slice(0, 120)}
            {template.promptText.length > 120 ? '...' : ''}
          </CardDescription>
        </CardHeader>

        <CardContent>
          <div className="flex flex-wrap gap-1.5">
            {template.categories.map((cat) => (
              <Badge key={cat.id} variant="secondary" className="text-xs">
                {cat.name}
              </Badge>
            ))}
          </div>
        </CardContent>

        <CardFooter className="text-xs text-muted-foreground">
          <div className="flex items-center gap-4">
            {template.estimatedDuration && (
              <span className="flex items-center gap-1">
                <Clock className="w-3 h-3" />
                {template.estimatedDuration}
              </span>
            )}
            {template.tags.length > 0 && (
              <span className="truncate">
                {template.tags.slice(0, 3).join(' · ')}
              </span>
            )}
          </div>
        </CardFooter>
      </Card>
    </Link>
  )
}
