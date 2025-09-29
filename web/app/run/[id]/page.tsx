"use client"

import { useState } from "react"
import { AppShell } from "@/components/app-shell"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Download, Copy, Share2, ExternalLink } from "lucide-react"

const mockReport = {
  id: "123",
  title: "Multi-Agent Research Systems: A Comprehensive Overview",
  createdAt: new Date("2025-01-15"),
  content: `# Multi-Agent Research Systems: A Comprehensive Overview

## Introduction

Multi-agent systems represent a paradigm in artificial intelligence where multiple autonomous agents interact to solve complex problems. These systems have gained significant attention in recent years due to their ability to handle distributed problem-solving and their applicability to real-world scenarios.

The emergence of multi-agent systems has revolutionized how we approach complex computational problems, enabling solutions that were previously intractable with single-agent approaches.

## Background and Historical Context

The field of multi-agent systems emerged from distributed artificial intelligence research in the 1980s. Early work focused on coordination mechanisms and communication protocols between agents. Researchers recognized that many real-world problems are inherently distributed and require multiple perspectives to solve effectively.

Key milestones in the development of multi-agent systems include the introduction of agent communication languages, the formalization of coordination protocols, and the development of learning algorithms that enable agents to adapt their behavior based on interactions with other agents.

## Current Approaches and Methodologies

Modern multi-agent systems leverage advanced machine learning techniques to enable agents to learn from their interactions and improve their collaborative capabilities over time. Contemporary research focuses on several key areas:

### Coordination Mechanisms

Effective coordination between agents is essential for system performance. Current approaches include market-based mechanisms, voting protocols, and negotiation strategies that allow agents to reach consensus on shared goals.

### Communication Protocols

Agent communication has evolved from simple message passing to sophisticated protocols that support complex information exchange, including beliefs, intentions, and goals. Standards like FIPA-ACL have provided a foundation for interoperable agent systems.

### Learning and Adaptation

Machine learning has become integral to multi-agent systems, with techniques like reinforcement learning enabling agents to optimize their behavior through experience. Multi-agent reinforcement learning presents unique challenges due to the non-stationary nature of the environment from each agent's perspective.

## Applications and Use Cases

Multi-agent systems have found applications across diverse domains:

- **Autonomous Vehicles**: Coordinating multiple vehicles to optimize traffic flow and safety
- **Smart Grids**: Managing distributed energy resources and balancing supply and demand
- **Financial Trading**: Automated trading systems that interact in complex market environments
- **Robotics**: Teams of robots collaborating on tasks like search and rescue or warehouse automation

## Challenges and Future Directions

Despite significant progress, several challenges remain in multi-agent systems research. Scalability continues to be a concern as the number of agents increases. Ensuring robust coordination in the presence of failures or adversarial agents is another critical challenge.

Future research directions include the integration of large language models into multi-agent frameworks, enabling more sophisticated reasoning and communication. The development of standardized benchmarks and evaluation metrics will also be crucial for advancing the field.

## Conclusion

Multi-agent systems represent a powerful approach to solving complex, distributed problems. As artificial intelligence continues to advance, the role of multi-agent systems in enabling collaborative intelligence will only grow in importance. The field stands at an exciting juncture, with opportunities to address fundamental challenges while expanding into new application domains.`,
  sources: [
    { id: "1", title: "Introduction to Multi-Agent Systems in AI Research", domain: "arxiv.org", url: "#" },
    { id: "2", title: "Collaborative AI: The Future of Research", domain: "nature.com", url: "#" },
    { id: "3", title: "Agent Communication Protocols", domain: "ieee.org", url: "#" },
    { id: "4", title: "Machine Learning in Multi-Agent Systems", domain: "jmlr.org", url: "#" },
    { id: "5", title: "Applications of Multi-Agent Systems", domain: "acm.org", url: "#" },
  ],
}

export default function RunPage({ params }: { params: { id: string } }) {
  const [copied, setCopied] = useState(false)

  const handleCopy = () => {
    navigator.clipboard.writeText(mockReport.content)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleShare = () => {
    navigator.clipboard.writeText(window.location.href)
    console.log("[v0] Link copied to clipboard")
  }

  return (
    <AppShell>
      <div className="container max-w-7xl mx-auto px-4 md:px-6 py-8">
        <div className="flex gap-8 lg:gap-12">
          {/* Table of Contents - Sticky on desktop */}
          <aside className="hidden lg:block w-64 shrink-0">
            <div className="sticky top-24 space-y-4">
              <h3 className="text-sm font-semibold text-foreground">Contents</h3>
              <nav className="space-y-2">
                {[
                  "Introduction",
                  "Background and Historical Context",
                  "Current Approaches and Methodologies",
                  "Applications and Use Cases",
                  "Challenges and Future Directions",
                  "Conclusion",
                ].map((section) => (
                  <a
                    key={section}
                    href={`#${section.toLowerCase().replace(/\s+/g, "-")}`}
                    className="block text-sm text-muted-foreground hover:text-[#6d28d9] transition-colors py-1 leading-relaxed"
                  >
                    {section}
                  </a>
                ))}
              </nav>
            </div>
          </aside>

          {/* Main Content */}
          <main className="flex-1 min-w-0">
            <article className="space-y-8">
              {/* Header */}
              <header className="space-y-4 pb-8 border-b border-border">
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <span>Run #{params.id}</span>
                  <span>•</span>
                  <time>{mockReport.createdAt.toLocaleDateString()}</time>
                </div>
                <h1 className="text-3xl md:text-4xl font-bold text-foreground text-balance">{mockReport.title}</h1>
              </header>

              {/* Content */}
              <div className="prose prose-sm md:prose-base max-w-none">
                <div className="text-foreground leading-relaxed whitespace-pre-wrap">{mockReport.content}</div>
              </div>

              {/* Sources */}
              <section className="pt-8 border-t border-border space-y-4">
                <h2 className="text-xl font-semibold text-foreground">Sources</h2>
                <div className="space-y-2">
                  {mockReport.sources.map((source, index) => (
                    <div
                      key={source.id}
                      className="flex items-start gap-3 p-4 rounded-2xl border border-border bg-card hover:bg-accent/50 transition-colors"
                    >
                      <span className="text-sm font-medium text-muted-foreground shrink-0">[{index + 1}]</span>
                      <div className="flex-1 min-w-0">
                        <h4 className="text-sm font-medium text-foreground">{source.title}</h4>
                        <Badge variant="secondary" className="mt-1 text-xs">
                          {source.domain}
                        </Badge>
                      </div>
                      <Button size="sm" variant="ghost" asChild>
                        <a href={source.url} target="_blank" rel="noopener noreferrer">
                          <ExternalLink className="w-4 h-4" />
                        </a>
                      </Button>
                    </div>
                  ))}
                </div>
              </section>
            </article>
          </main>

          {/* Actions Sidebar - Sticky on desktop */}
          <aside className="hidden md:block w-48 shrink-0">
            <div className="sticky top-24 space-y-2">
              <h3 className="text-sm font-semibold text-foreground mb-3">Actions</h3>
              <div className="space-y-2">
                <Button
                  variant="outline"
                  size="sm"
                  className="w-full justify-start rounded-2xl bg-transparent"
                  onClick={() => console.log("[v0] Export markdown")}
                >
                  <Download className="w-4 h-4 mr-2" />
                  Export .md
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  className="w-full justify-start rounded-2xl bg-transparent"
                  onClick={() => console.log("[v0] Export PDF")}
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
                  {copied ? "Copied!" : "Copy"}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  className="w-full justify-start rounded-2xl bg-transparent"
                  onClick={handleShare}
                >
                  <Share2 className="w-4 h-4 mr-2" />
                  Share Link
                </Button>
              </div>
            </div>
          </aside>
        </div>

        {/* Mobile Actions - Fixed at bottom */}
        <div className="md:hidden fixed bottom-0 left-0 right-0 p-4 bg-background border-t border-border">
          <div className="flex gap-2">
            <Button size="sm" variant="outline" className="flex-1 rounded-2xl bg-transparent" onClick={handleCopy}>
              <Copy className="w-4 h-4 mr-2" />
              {copied ? "Copied!" : "Copy"}
            </Button>
            <Button size="sm" variant="outline" className="flex-1 rounded-2xl bg-transparent" onClick={handleShare}>
              <Share2 className="w-4 h-4 mr-2" />
              Share
            </Button>
            <Button
              size="sm"
              className="flex-1 rounded-2xl bg-[#6d28d9] hover:bg-[#7c3aed]"
              onClick={() => console.log("[v0] Export")}
            >
              <Download className="w-4 h-4 mr-2" />
              Export
            </Button>
          </div>
        </div>
      </div>
    </AppShell>
  )
}
