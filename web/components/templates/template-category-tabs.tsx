'use client'

import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import type { TemplateCategory } from '@/types/contentful'

interface TemplateCategoryTabsProps {
  categories: TemplateCategory[]
  activeCategory: string
  onCategoryChange: (slug: string) => void
}

export function TemplateCategoryTabs({
  categories,
  activeCategory,
  onCategoryChange,
}: TemplateCategoryTabsProps) {
  return (
    <Tabs value={activeCategory} onValueChange={onCategoryChange}>
      <TabsList className="flex-wrap h-auto gap-1 overflow-x-auto">
        <TabsTrigger value="all">All</TabsTrigger>
        {categories.map((cat) => (
          <TabsTrigger key={cat.id} value={cat.slug}>
            {cat.name}
          </TabsTrigger>
        ))}
      </TabsList>
    </Tabs>
  )
}
