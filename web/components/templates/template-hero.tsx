import Link from 'next/link'
import Image from 'next/image'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { DifficultyBadge } from './difficulty-badge'
import { ArrowRight, Clock, FileText } from 'lucide-react'
import type { ResearchTemplate } from '@/types/contentful'

interface TemplateHeroProps {
  templates: ResearchTemplate[]
}

export function TemplateHero({ templates }: TemplateHeroProps) {
  if (templates.length === 0) return null

  return (
    <section className="space-y-4">
      <h2 className="text-lg font-semibold text-foreground">Featured Templates</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {templates.slice(0, 3).map((template) => (
          <Link
            key={template.id}
            href={`/templates/${template.slug}`}
            className="group block"
          >
            <Card className="h-full border-primary/20 bg-gradient-to-br from-card to-primary/5 transition-all duration-200 hover:shadow-lg hover:-translate-y-1">
              <CardHeader>
                <div className="flex items-center gap-3 mb-2">
                  {template.icon ? (
                    <Image
                      src={template.icon.url}
                      alt={template.icon.alt}
                      width={48}
                      height={48}
                      className="rounded-lg"
                    />
                  ) : (
                    <div className="w-12 h-12 rounded-lg bg-gradient-to-r from-purple-600 to-blue-600 flex items-center justify-center">
                      <FileText className="w-6 h-6 text-white" />
                    </div>
                  )}
                  <div className="flex-1">
                    <CardTitle className="text-lg group-hover:text-primary transition-colors">
                      {template.title}
                    </CardTitle>
                    <div className="flex items-center gap-2 mt-1">
                      <DifficultyBadge difficulty={template.difficulty} />
                      {template.estimatedDuration && (
                        <span className="flex items-center gap-1 text-xs text-muted-foreground">
                          <Clock className="w-3 h-3" />
                          {template.estimatedDuration}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
                <CardDescription className="line-clamp-3">
                  {template.promptText.slice(0, 150)}
                  {template.promptText.length > 150 ? '...' : ''}
                </CardDescription>
              </CardHeader>

              <CardContent>
                <div className="flex items-center justify-between">
                  <div className="flex flex-wrap gap-1.5">
                    {template.categories.slice(0, 2).map((cat) => (
                      <Badge key={cat.id} variant="secondary" className="text-xs">
                        {cat.name}
                      </Badge>
                    ))}
                  </div>
                  <Button variant="ghost" size="sm" className="gap-1 text-xs">
                    View <ArrowRight className="w-3 h-3" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>
    </section>
  )
}
