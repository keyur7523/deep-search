import type { OutlineItem } from '@/lib/types'

export function buildOutlineFromReport(markdown: string): OutlineItem[] {
  const items: OutlineItem[] = []
  const lines = markdown.split('\n')
  let index = 1
  let current: OutlineItem | null = null

  for (const line of lines) {
    const heading = line.match(/^#{1,3}\s+(.+)$/)
    if (heading) {
      const title = heading[1]?.trim()
      if (!title) continue
      current = {
        id: `outline-${index}`,
        index,
        title,
        brief: '',
        status: 'done',
      }
      items.push(current)
      index += 1
      continue
    }

    if (current && !current.brief) {
      const text = line.trim()
      if (text && !text.startsWith('#')) {
        current.brief = text.slice(0, 160)
      }
    }
  }

  return items
}
