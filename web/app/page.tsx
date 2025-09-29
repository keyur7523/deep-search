import Link from "next/link"
import { Button } from "@/components/ui/button"
import { Sparkles, BookOpen, FileText, Search } from "lucide-react"

export default function HomePage() {
  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="sticky top-0 z-50 w-full border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="container flex h-16 items-center justify-between px-4 md:px-6">
          <Link href="/" className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-[#6d28d9] flex items-center justify-center">
              <svg viewBox="0 0 24 24" fill="none" className="w-5 h-5 text-white" xmlns="http://www.w3.org/2000/svg">
                <circle cx="12" cy="12" r="4" stroke="currentColor" strokeWidth="2" />
                <circle cx="12" cy="12" r="8" stroke="currentColor" strokeWidth="1.5" opacity="0.5" />
              </svg>
            </div>
            <span className="font-semibold text-lg text-foreground">Iris Research</span>
          </Link>

          <nav className="hidden md:flex items-center gap-6">
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
      </header>

      {/* Hero Section */}
      <main className="flex-1">
        <section className="container px-4 md:px-6 py-20 md:py-32">
          <div className="max-w-4xl mx-auto text-center space-y-8">
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-[#ede9fe] text-[#6d28d9] text-sm font-medium">
              <Sparkles className="w-4 h-4" />
              Multi-Agent Research Platform
            </div>

            <h1 className="text-4xl md:text-6xl lg:text-7xl font-bold text-foreground tracking-tight text-balance">
              Deep research, powered by AI agents
            </h1>

            <p className="text-lg md:text-xl text-muted-foreground max-w-2xl mx-auto text-pretty">
              Iris Research orchestrates multiple AI agents to explore topics comprehensively, gather sources, and
              generate detailed reports with citations.
            </p>

            <div className="flex flex-col sm:flex-row items-center justify-center gap-4 pt-4">
              <Button asChild size="lg" className="bg-[#6d28d9] hover:bg-[#7c3aed] text-white rounded-2xl px-8 h-12">
                <Link href="/app">New Research</Link>
              </Button>
            </div>
          </div>
        </section>

        {/* Features Section */}
        <section className="container px-4 md:px-6 py-20 border-t border-border">
          <div className="max-w-6xl mx-auto">
            <div className="grid md:grid-cols-3 gap-8 md:gap-12">
              <div className="space-y-4">
                <div className="w-12 h-12 rounded-2xl bg-[#ede9fe] flex items-center justify-center">
                  <Search className="w-6 h-6 text-[#6d28d9]" />
                </div>
                <h3 className="text-xl font-semibold text-foreground">Multi-Round Search</h3>
                <p className="text-muted-foreground leading-relaxed">
                  AI agents perform multiple search rounds, refining queries and gathering comprehensive sources for
                  each section of your research.
                </p>
              </div>

              <div className="space-y-4">
                <div className="w-12 h-12 rounded-2xl bg-[#ede9fe] flex items-center justify-center">
                  <BookOpen className="w-6 h-6 text-[#6d28d9]" />
                </div>
                <h3 className="text-xl font-semibold text-foreground">Intelligent Reflection</h3>
                <p className="text-muted-foreground leading-relaxed">
                  Agents analyze gathered information, identify gaps, and reflect on findings to ensure thorough
                  coverage of your topic.
                </p>
              </div>

              <div className="space-y-4">
                <div className="w-12 h-12 rounded-2xl bg-[#ede9fe] flex items-center justify-center">
                  <FileText className="w-6 h-6 text-[#6d28d9]" />
                </div>
                <h3 className="text-xl font-semibold text-foreground">Cited Reports</h3>
                <p className="text-muted-foreground leading-relaxed">
                  Generate well-structured reports with proper citations, source tracking, and export options for
                  markdown and PDF formats.
                </p>
              </div>
            </div>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="border-t border-border py-8">
        <div className="container px-4 md:px-6">
          <div className="flex flex-col md:flex-row items-center justify-between gap-4">
            <p className="text-sm text-muted-foreground">© 2025 Iris Research. All rights reserved.</p>
            <nav className="flex items-center gap-6">
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
