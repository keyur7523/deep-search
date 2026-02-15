import type { Document } from '@contentful/rich-text-types'

export interface TemplateCategory {
  id: string
  name: string
  slug: string
  description?: string
  displayOrder: number
  color?: string
}

export interface ResearchTemplate {
  id: string
  title: string
  slug: string
  description: Document
  promptText: string
  categories: TemplateCategory[]
  icon?: {
    url: string
    alt: string
    width: number
    height: number
  }
  difficulty: 'beginner' | 'intermediate' | 'advanced'
  featured: boolean
  sortOrder: number
  estimatedDuration?: string
  tags: string[]
}
