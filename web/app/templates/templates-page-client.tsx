'use client'

import { useState, useCallback, useMemo } from 'react'
import { TemplateCategoryTabs } from '@/components/templates/template-category-tabs'
import { TemplateSearch } from '@/components/templates/template-search'
import { TemplateCard } from '@/components/templates/template-card'
import { StaggerContainer, StaggerItem } from '@/components/ui/animations'
import { Search } from 'lucide-react'
import type { ResearchTemplate, TemplateCategory } from '@/types/contentful'
import type { Document, Block, Inline, Text } from '@contentful/rich-text-types'

function extractPlainText(doc: Document): string {
  const texts: string[] = []
  function walk(node: Document | Block | Inline | Text) {
    if ('value' in node && typeof node.value === 'string') {
      texts.push(node.value)
    }
    if ('content' in node && Array.isArray(node.content)) {
      node.content.forEach(walk)
    }
  }
  walk(doc)
  return texts.join(' ')
}

interface TemplatesPageClientProps {
  templates: ResearchTemplate[]
  categories: TemplateCategory[]
}

export function TemplatesPageClient({ templates, categories }: TemplatesPageClientProps) {
  const [activeCategory, setActiveCategory] = useState('all')
  const [searchQuery, setSearchQuery] = useState('')

  const filteredTemplates = useMemo(() => {
    let filtered = templates

    if (activeCategory !== 'all') {
      filtered = filtered.filter((t) =>
        t.categories.some((cat) => cat.slug === activeCategory)
      )
    }

    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase()
      filtered = filtered.filter((t) => {
        const titleMatch = t.title.toLowerCase().includes(query)
        const tagMatch = t.tags.some((tag) => tag.toLowerCase().includes(query))
        const promptMatch = t.promptText.toLowerCase().includes(query)
        let descriptionMatch = false
        try {
          const plainText = extractPlainText(t.description)
          descriptionMatch = plainText.toLowerCase().includes(query)
        } catch {
          // ignore rich text parsing errors
        }
        return titleMatch || tagMatch || promptMatch || descriptionMatch
      })
    }

    return filtered
  }, [templates, activeCategory, searchQuery])

  const handleSearch = useCallback((query: string) => {
    setSearchQuery(query)
  }, [])

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row gap-4">
        <TemplateCategoryTabs
          categories={categories}
          activeCategory={activeCategory}
          onCategoryChange={setActiveCategory}
        />
      </div>

      <TemplateSearch onSearch={handleSearch} resultCount={filteredTemplates.length} />

      {filteredTemplates.length === 0 ? (
        <div className="text-center py-16 space-y-3">
          <Search className="w-10 h-10 mx-auto text-muted-foreground/50" />
          <p className="text-lg font-medium text-foreground">
            {searchQuery || activeCategory !== 'all'
              ? 'No templates match your search'
              : 'No templates yet'}
          </p>
          <p className="text-sm text-muted-foreground">
            {searchQuery || activeCategory !== 'all'
              ? 'Try a different filter or search term.'
              : 'Check back soon!'}
          </p>
        </div>
      ) : (
        <StaggerContainer className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredTemplates.map((template) => (
            <StaggerItem key={template.id}>
              <TemplateCard template={template} />
            </StaggerItem>
          ))}
        </StaggerContainer>
      )}
    </div>
  )
}
