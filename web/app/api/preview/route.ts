import { draftMode } from 'next/headers'
import { redirect } from 'next/navigation'
import { NextRequest } from 'next/server'
import { getTemplateBySlug } from '@/lib/contentful'

export async function GET(request: NextRequest) {
  const { searchParams } = request.nextUrl
  const secret = searchParams.get('secret')
  const slug = searchParams.get('slug')

  if (secret !== process.env.CONTENTFUL_PREVIEW_TOKEN) {
    return new Response('Invalid secret', { status: 401 })
  }

  if (!slug) {
    return new Response('Missing slug', { status: 400 })
  }

  const template = await getTemplateBySlug(slug, true)
  if (!template) {
    return new Response('Template not found', { status: 404 })
  }

  draftMode().enable()
  redirect(`/templates/${slug}`)
}
