import { draftMode } from 'next/headers'
import { notFound } from 'next/navigation'
import { getTemplateBySlug, getTemplates } from '@/lib/contentful'
import { TemplateDetail } from '@/components/templates/template-detail'
import { PreviewBanner } from '@/components/templates/preview-banner'
import Link from 'next/link'
import { ThemeToggle } from '@/components/theme-toggle'
import type { Metadata } from 'next'

export const revalidate = 60

interface PageProps {
  params: { slug: string }
}

export async function generateStaticParams() {
  const templates = await getTemplates()
  return templates.map((t) => ({ slug: t.slug }))
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const template = await getTemplateBySlug(params.slug)
  if (!template) {
    return { title: 'Template Not Found | DeepSearch' }
  }

  const description = template.promptText.slice(0, 160)

  return {
    title: `${template.title} — Research Template | DeepSearch`,
    description,
    openGraph: {
      title: `${template.title} — Research Template | DeepSearch`,
      description,
      url: `https://deep-search-two.vercel.app/templates/${template.slug}`,
    },
    alternates: {
      canonical: `https://deep-search-two.vercel.app/templates/${template.slug}`,
    },
  }
}

export default async function TemplateDetailPage({ params }: PageProps) {
  const { isEnabled: isPreview } = draftMode()
  const template = await getTemplateBySlug(params.slug, isPreview)

  if (!template) {
    notFound()
  }

  const jsonLd = {
    '@context': 'https://schema.org',
    '@type': 'HowTo',
    name: template.title,
    description: template.promptText.slice(0, 200),
    step: [
      {
        '@type': 'HowToStep',
        text: 'Use this template in DeepSearch',
      },
    ],
  }

  return (
    <div className="min-h-screen flex flex-col">
      {isPreview && <PreviewBanner />}

      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />

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
            <ThemeToggle variant="ghost" size="icon" />
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 w-full max-w-6xl mx-auto px-4 md:px-6 py-12">
        <TemplateDetail template={template} />
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
