import { createClient, type ContentfulClientApi, type Entry, type Asset } from 'contentful'
import type { TemplateCategory, ResearchTemplate } from '@/types/contentful'

let _client: ContentfulClientApi<undefined> | null = null
let _previewClient: ContentfulClientApi<undefined> | null = null

function isConfigured(): boolean {
  return !!(process.env.CONTENTFUL_SPACE_ID && process.env.CONTENTFUL_ACCESS_TOKEN)
}

function getDeliveryClient(): ContentfulClientApi<undefined> | null {
  if (!isConfigured()) return null
  if (!_client) {
    _client = createClient({
      space: process.env.CONTENTFUL_SPACE_ID!,
      accessToken: process.env.CONTENTFUL_ACCESS_TOKEN!,
      environment: process.env.CONTENTFUL_ENVIRONMENT || 'master',
    })
  }
  return _client
}

function getPreviewClient(): ContentfulClientApi<undefined> | null {
  if (!process.env.CONTENTFUL_SPACE_ID || !process.env.CONTENTFUL_PREVIEW_TOKEN) return null
  if (!_previewClient) {
    _previewClient = createClient({
      space: process.env.CONTENTFUL_SPACE_ID!,
      accessToken: process.env.CONTENTFUL_PREVIEW_TOKEN!,
      environment: process.env.CONTENTFUL_ENVIRONMENT || 'master',
      host: 'preview.contentful.com',
    })
  }
  return _previewClient
}

function getClient(preview = false) {
  return preview ? getPreviewClient() : getDeliveryClient()
}

function parseCategory(entry: Entry): TemplateCategory {
  const fields = entry.fields as Record<string, unknown>
  return {
    id: entry.sys.id,
    name: (fields.name as string) || '',
    slug: (fields.slug as string) || '',
    description: fields.description as string | undefined,
    displayOrder: (fields.displayOrder as number) ?? 100,
    color: fields.color as string | undefined,
  }
}

function parseTemplate(entry: Entry): ResearchTemplate {
  const fields = entry.fields as Record<string, unknown>

  const categoryRefs = (fields.category as Entry[] | undefined) || []
  const categories = categoryRefs
    .filter((ref): ref is Entry => ref?.sys?.type === 'Entry')
    .map(parseCategory)

  const iconAsset = fields.icon as Asset | undefined
  let icon: ResearchTemplate['icon'] | undefined
  if (iconAsset?.fields?.file) {
    const file = iconAsset.fields.file as Record<string, unknown>
    const details = file.details as Record<string, unknown> | undefined
    const image = details?.image as Record<string, unknown> | undefined
    icon = {
      url: `https:${file.url as string}`,
      alt: (iconAsset.fields.title as string) || '',
      width: (image?.width as number) || 200,
      height: (image?.height as number) || 200,
    }
  }

  return {
    id: entry.sys.id,
    title: (fields.title as string) || '',
    slug: (fields.slug as string) || '',
    description: fields.description as ResearchTemplate['description'],
    promptText: (fields.promptText as string) || '',
    categories,
    icon,
    difficulty: (fields.difficulty as ResearchTemplate['difficulty']) || 'beginner',
    featured: (fields.featured as boolean) ?? false,
    sortOrder: (fields.sortOrder as number) ?? 100,
    estimatedDuration: fields.estimatedDuration as string | undefined,
    tags: (fields.tags as string[]) || [],
  }
}

export async function getCategories(preview = false): Promise<TemplateCategory[]> {
  try {
    const client = getClient(preview)
    if (!client) return []
    const entries = await client.getEntries({
      content_type: 'templateCategory',
      order: ['fields.displayOrder'],
    })
    return entries.items.map(parseCategory)
  } catch {
    return []
  }
}

export async function getTemplates(options?: {
  category?: string
  featured?: boolean
  preview?: boolean
}): Promise<ResearchTemplate[]> {
  try {
    const query: Record<string, unknown> = {
      content_type: 'researchTemplate',
      order: ['fields.sortOrder'],
      include: 2,
    }

    if (options?.featured !== undefined) {
      query['fields.featured'] = options.featured
    }

    if (options?.category) {
      query['fields.category.sys.contentType.sys.id'] = 'templateCategory'
      query['fields.category.fields.slug'] = options.category
    }

    const client = getClient(options?.preview)
    if (!client) return []
    const entries = await client.getEntries(query)
    return entries.items.map(parseTemplate)
  } catch {
    return []
  }
}

export async function getTemplateBySlug(
  slug: string,
  preview = false
): Promise<ResearchTemplate | null> {
  try {
    const client = getClient(preview)
    if (!client) return null
    const entries = await client.getEntries({
      content_type: 'researchTemplate',
      'fields.slug': slug,
      limit: 1,
      include: 2,
    })
    if (entries.items.length === 0) return null
    return parseTemplate(entries.items[0])
  } catch {
    return null
  }
}

export async function getFeaturedTemplates(preview = false): Promise<ResearchTemplate[]> {
  return getTemplates({ featured: true, preview })
}
