import { documentToReactComponents, type Options } from '@contentful/rich-text-react-renderer'
import { BLOCKS, INLINES, MARKS, type Document } from '@contentful/rich-text-types'
import Image from 'next/image'
import { cn } from '@/lib/utils'

const renderOptions: Options = {
  renderMark: {
    [MARKS.BOLD]: (text) => <strong className="font-semibold">{text}</strong>,
    [MARKS.ITALIC]: (text) => <em>{text}</em>,
    [MARKS.CODE]: (text) => (
      <code className="rounded bg-muted px-1.5 py-0.5 text-sm font-mono">{text}</code>
    ),
  },
  renderNode: {
    [BLOCKS.PARAGRAPH]: (_node, children) => (
      <p className="text-base text-foreground leading-7 mb-4">{children}</p>
    ),
    [BLOCKS.HEADING_2]: (_node, children) => (
      <h2 className="text-2xl font-semibold text-foreground mt-8 mb-4">{children}</h2>
    ),
    [BLOCKS.HEADING_3]: (_node, children) => (
      <h3 className="text-xl font-semibold text-foreground mt-6 mb-3">{children}</h3>
    ),
    [BLOCKS.HEADING_4]: (_node, children) => (
      <h4 className="text-lg font-medium text-foreground mt-4 mb-2">{children}</h4>
    ),
    [BLOCKS.UL_LIST]: (_node, children) => (
      <ul className="list-disc list-inside space-y-1 mb-4 text-foreground">{children}</ul>
    ),
    [BLOCKS.OL_LIST]: (_node, children) => (
      <ol className="list-decimal list-inside space-y-1 mb-4 text-foreground">{children}</ol>
    ),
    [BLOCKS.LIST_ITEM]: (_node, children) => (
      <li className="text-base leading-7">{children}</li>
    ),
    [BLOCKS.QUOTE]: (_node, children) => (
      <blockquote className="border-l-4 border-primary/30 pl-4 italic text-muted-foreground mb-4">
        {children}
      </blockquote>
    ),
    [BLOCKS.HR]: () => <hr className="my-8 border-border" />,
    [BLOCKS.EMBEDDED_ASSET]: (node) => {
      const file = node.data?.target?.fields?.file
      const title = node.data?.target?.fields?.title as string | undefined
      if (!file) return null
      const { url, details } = file as Record<string, unknown>
      const image = (details as Record<string, unknown>)?.image as Record<string, unknown> | undefined
      return (
        <div className="my-6">
          <Image
            src={`https:${url as string}`}
            alt={title || ''}
            width={(image?.width as number) || 800}
            height={(image?.height as number) || 400}
            className="rounded-lg"
          />
        </div>
      )
    },
    [INLINES.HYPERLINK]: (node, children) => (
      <a
        href={node.data.uri as string}
        target="_blank"
        rel="noopener noreferrer"
        className="text-primary underline underline-offset-4 hover:text-primary/80 transition-colors"
      >
        {children}
      </a>
    ),
  },
}

interface RichTextRendererProps {
  document: Document
  className?: string
}

export function RichTextRenderer({ document, className }: RichTextRendererProps) {
  if (!document) return null
  return (
    <div className={cn('prose-custom', className)}>
      {documentToReactComponents(document, renderOptions)}
    </div>
  )
}
