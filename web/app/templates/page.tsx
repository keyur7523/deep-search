import { draftMode } from 'next/headers'
import { getCategories, getTemplates, getFeaturedTemplates } from '@/lib/contentful'
import { PreviewBanner } from '@/components/templates/preview-banner'
import { TemplateHero } from '@/components/templates/template-hero'
import { TemplatesPageClient } from './templates-page-client'
import Link from 'next/link'
import { ThemeToggle } from '@/components/theme-toggle'

export const revalidate = 60

export const metadata = {
  title: 'Research Templates | DeepSearch',
  description: 'Browse pre-built research prompt templates for market analysis, literature reviews, competitive landscapes, and more.',
  openGraph: {
    title: 'Research Templates | DeepSearch',
    description: 'Browse pre-built research prompt templates for market analysis, literature reviews, competitive landscapes, and more.',
    url: 'https://deep-search-two.vercel.app/templates',
  },
  alternates: {
    canonical: 'https://deep-search-two.vercel.app/templates',
  },
}

export default async function TemplatesPage() {
  const { isEnabled: isPreview } = draftMode()

  const [categories, templates, featuredTemplates] = await Promise.all([
    getCategories(isPreview),
    getTemplates({ preview: isPreview }),
    getFeaturedTemplates(isPreview),
  ])

  return (
    <div className="min-h-screen flex flex-col">
      {isPreview && <PreviewBanner />}

      {/* Header */}
      <header className="sticky top-0 z-50 w-full border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="w-full flex h-16 items-center justify-between px-4 md:px-6">
          <Link href="/" className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-full bg-gradient-to-r from-purple-600 to-blue-600 flex items-center justify-center shadow-lg">
              <svg viewBox="0 0 24 24" fill="none" className="w-7 h-7 text-white" xmlns="http://www.w3.org/2000/svg">
                <circle cx="12" cy="12" r="4" stroke="currentColor" strokeWidth="2" />
                <circle cx="12" cy="12" r="8" stroke="currentColor" strokeWidth="1.5" opacity="0.5" />
              </svg>
            </div>
            <span className="font-semibold text-lg text-foreground">Deep Research</span>
          </Link>

          <div className="flex items-center gap-3">
            <nav className="hidden md:flex items-center gap-6 mr-2">
              <Link href="/templates" className="text-sm font-medium text-foreground">
                Templates
              </Link>
              <Link href="/docs" className="text-sm text-muted-foreground hover:text-foreground transition-colors">
                Docs
              </Link>
              <Link href="/changelog" className="text-sm text-muted-foreground hover:text-foreground transition-colors">
                Changelog
              </Link>
              <Link href="/contact" className="text-sm text-muted-foreground hover:text-foreground transition-colors">
                Contact
              </Link>
            </nav>
            <ThemeToggle variant="ghost" size="icon" />
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 w-full max-w-6xl mx-auto px-4 md:px-6 py-12 space-y-10">
        {/* Page Header */}
        <div className="text-center space-y-3">
          <h1 className="text-4xl md:text-5xl font-bold tracking-tight">
            <span className="bg-gradient-to-r from-purple-600 to-blue-600 bg-clip-text text-transparent">Research</span>{' '}
            <span className="text-foreground">Templates</span>
          </h1>
          <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
            Browse pre-built research prompt templates for market analysis, literature reviews,
            competitive landscapes, and more.
          </p>
        </div>

        {/* Featured Templates */}
        <TemplateHero templates={featuredTemplates} />

        {/* Filterable Grid */}
        <TemplatesPageClient templates={templates} categories={categories} />
      </main>

      {/* Footer */}
      <footer className="border-t border-border py-8">
        <div className="w-full px-4 md:px-6">
          <div className="flex flex-col md:flex-row items-center justify-between gap-4">
            <p className="text-sm text-muted-foreground">&copy; 2025 Deep Research. All rights reserved.</p>
            <nav className="flex items-center gap-6 mr-4 md:mr-6">
              <Link href="/templates" className="text-sm text-muted-foreground hover:text-foreground transition-colors">
                Templates
              </Link>
              <Link href="/docs" className="text-sm text-muted-foreground hover:text-foreground transition-colors">
                Docs
              </Link>
              <Link href="/changelog" className="text-sm text-muted-foreground hover:text-foreground transition-colors">
                Changelog
              </Link>
              <Link href="/contact" className="text-sm text-muted-foreground hover:text-foreground transition-colors">
                Contact
              </Link>
            </nav>
          </div>
        </div>
      </footer>
    </div>
  )
}
