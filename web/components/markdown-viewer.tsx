"use client"

import { useState } from "react"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Button } from "@/components/ui/button"
import { Download, Copy, RefreshCw, Lightbulb } from "lucide-react"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { Textarea } from "@/components/ui/textarea"

interface MarkdownViewerProps {
  content: string
  onExportMd?: () => void
  onExportPdf?: () => void
  onRegenerate?: (paragraphId: string) => void
  onAddHint?: (paragraphId: string, hint: string) => void
}

export function MarkdownViewer({ content, onExportMd, onExportPdf, onRegenerate, onAddHint }: MarkdownViewerProps) {
  const [hintText, setHintText] = useState("")

  const handleCopy = () => {
    navigator.clipboard.writeText(content)
    console.log("[v0] Copied content to clipboard")
  }

  const handleAddHint = () => {
    if (hintText.trim()) {
      onAddHint?.("paragraph-1", hintText)
      setHintText("")
    }
  }

  return (
    <div className="flex gap-6 h-full">
      {/* Table of Contents - Hidden on mobile */}
      <aside className="hidden lg:block w-56 shrink-0">
        <div className="sticky top-6 space-y-2">
          <h3 className="text-sm font-semibold text-foreground mb-3">Contents</h3>
          <nav className="space-y-1">
            {["Introduction", "Background", "Methodology", "Results", "Conclusion"].map((section) => (
              <a
                key={section}
                href={`#${section.toLowerCase()}`}
                className="block text-sm text-muted-foreground hover:text-[#6d28d9] transition-colors py-1"
              >
                {section}
              </a>
            ))}
          </nav>
        </div>
      </aside>

      {/* Main Content */}
      <div className="flex-1 min-w-0">
        <ScrollArea className="h-[calc(100vh-12rem)]">
          <div className="prose prose-sm max-w-none">
            <div className="text-foreground leading-relaxed whitespace-pre-wrap">{content}</div>
          </div>
        </ScrollArea>
      </div>

      {/* Actions Sidebar - Hidden on mobile */}
      <aside className="hidden md:block w-48 shrink-0">
        <div className="sticky top-6 space-y-2">
          <h3 className="text-sm font-semibold text-foreground mb-3">Actions</h3>
          <div className="space-y-2">
            <Button
              variant="outline"
              size="sm"
              className="w-full justify-start rounded-2xl bg-transparent"
              onClick={onExportMd}
            >
              <Download className="w-4 h-4 mr-2" />
              Export .md
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="w-full justify-start rounded-2xl bg-transparent"
              onClick={onExportPdf}
            >
              <Download className="w-4 h-4 mr-2" />
              Export .pdf
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="w-full justify-start rounded-2xl bg-transparent"
              onClick={handleCopy}
            >
              <Copy className="w-4 h-4 mr-2" />
              Copy
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="w-full justify-start rounded-2xl bg-transparent"
              onClick={() => onRegenerate?.("paragraph-1")}
            >
              <RefreshCw className="w-4 h-4 mr-2" />
              Regenerate
            </Button>

            <Dialog>
              <DialogTrigger asChild>
                <Button variant="outline" size="sm" className="w-full justify-start rounded-2xl bg-transparent">
                  <Lightbulb className="w-4 h-4 mr-2" />
                  Add Hint
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Add Hint</DialogTitle>
                </DialogHeader>
                <div className="space-y-4 pt-4">
                  <Textarea
                    placeholder="Enter your hint or guidance for regeneration..."
                    value={hintText}
                    onChange={(e) => setHintText(e.target.value)}
                    className="min-h-32 rounded-2xl"
                  />
                  <Button onClick={handleAddHint} className="w-full rounded-2xl bg-[#6d28d9] hover:bg-[#7c3aed]">
                    Submit Hint
                  </Button>
                </div>
              </DialogContent>
            </Dialog>
          </div>
        </div>
      </aside>
    </div>
  )
}
