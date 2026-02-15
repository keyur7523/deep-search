'use client'

import { useState } from 'react'
import Link from 'next/link'
import Image from 'next/image'
import { useRouter } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { DifficultyBadge } from './difficulty-badge'
import { RichTextRenderer } from './rich-text-renderer'
import { ArrowLeft, Clock, Copy, Check, Sparkles, FileText, Tag } from 'lucide-react'
import type { ResearchTemplate } from '@/types/contentful'

interface TemplateDetailProps {
  template: ResearchTemplate
}

export function TemplateDetail({ template }: TemplateDetailProps) {
  const router = useRouter()
  const [copied, setCopied] = useState(false)

  const handleUseTemplate = () => {
    router.push(`/app?prompt=${encodeURIComponent(template.promptText)}`)
  }

  const handleCopyPrompt = async () => {
    await navigator.clipboard.writeText(template.promptText)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="max-w-3xl mx-auto space-y-8">
      <Link
        href="/templates"
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors"
      >
        <ArrowLeft className="w-4 h-4" />
        Back to Templates
      </Link>

      <div className="space-y-4">
        <div className="flex items-start gap-4">
          {template.icon ? (
            <Image
              src={template.icon.url}
              alt={template.icon.alt}
              width={64}
              height={64}
              className="rounded-xl"
            />
          ) : (
            <div className="w-16 h-16 rounded-xl bg-gradient-to-r from-purple-600 to-blue-600 flex items-center justify-center flex-shrink-0">
              <FileText className="w-8 h-8 text-white" />
            </div>
          )}
          <div className="space-y-2">
            <h1 className="text-3xl font-bold text-foreground">{template.title}</h1>
            <div className="flex flex-wrap items-center gap-3">
              <DifficultyBadge difficulty={template.difficulty} />
              {template.estimatedDuration && (
                <span className="flex items-center gap-1 text-sm text-muted-foreground">
                  <Clock className="w-4 h-4" />
                  {template.estimatedDuration}
                </span>
              )}
              {template.categories.map((cat) => (
                <Badge key={cat.id} variant="secondary">
                  {cat.name}
                </Badge>
              ))}
            </div>
          </div>
        </div>

        {template.tags.length > 0 && (
          <div className="flex flex-wrap items-center gap-2">
            <Tag className="w-3.5 h-3.5 text-muted-foreground" />
            {template.tags.map((tag) => (
              <Badge key={tag} variant="outline" className="text-xs">
                {tag}
              </Badge>
            ))}
          </div>
        )}
      </div>

      <div className="rounded-2xl border bg-card p-6 space-y-4">
        <h2 className="text-sm font-medium text-muted-foreground uppercase tracking-wider">Prompt</h2>
        <p className="text-foreground whitespace-pre-wrap leading-7">{template.promptText}</p>
        <div className="flex flex-col sm:flex-row gap-3 pt-2">
          <Button
            onClick={handleUseTemplate}
            className="bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-700 hover:to-blue-700 text-white rounded-2xl h-11"
          >
            <Sparkles className="w-4 h-4 mr-2" />
            Use This Template
          </Button>
          <Button variant="outline" onClick={handleCopyPrompt} className="rounded-2xl h-11">
            {copied ? (
              <>
                <Check className="w-4 h-4 mr-2" />
                Copied!
              </>
            ) : (
              <>
                <Copy className="w-4 h-4 mr-2" />
                Copy Prompt
              </>
            )}
          </Button>
        </div>
      </div>

      <div className="space-y-4">
        <h2 className="text-xl font-semibold text-foreground">Description</h2>
        <RichTextRenderer document={template.description} />
      </div>
    </div>
  )
}
