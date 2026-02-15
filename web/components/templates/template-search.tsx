'use client'

import { useState, useEffect } from 'react'
import { Input } from '@/components/ui/input'
import { Search } from 'lucide-react'

interface TemplateSearchProps {
  onSearch: (query: string) => void
  resultCount: number
}

export function TemplateSearch({ onSearch, resultCount }: TemplateSearchProps) {
  const [value, setValue] = useState('')

  useEffect(() => {
    const timer = setTimeout(() => {
      onSearch(value)
    }, 300)
    return () => clearTimeout(timer)
  }, [value, onSearch])

  return (
    <div className="relative">
      <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
      <Input
        placeholder="Search templates by name, tags, or description..."
        value={value}
        onChange={(e) => setValue(e.target.value)}
        className="pl-9 rounded-2xl"
      />
      {value && (
        <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-muted-foreground">
          {resultCount} result{resultCount !== 1 ? 's' : ''}
        </span>
      )}
    </div>
  )
}
