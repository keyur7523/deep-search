import { revalidatePath, revalidateTag } from 'next/cache'
import { NextRequest, NextResponse } from 'next/server'

export async function POST(request: NextRequest) {
  const secret = request.headers.get('x-contentful-webhook-secret')

  if (secret !== process.env.CONTENTFUL_REVALIDATE_SECRET) {
    return NextResponse.json({ message: 'Invalid secret' }, { status: 401 })
  }

  try {
    revalidateTag('templates')
    revalidatePath('/templates')

    const body = await request.json().catch(() => null)
    const slug = body?.fields?.slug?.['en-US'] as string | undefined
    if (slug) {
      revalidatePath(`/templates/${slug}`)
    }

    return NextResponse.json({ revalidated: true })
  } catch {
    return NextResponse.json({ message: 'Error revalidating' }, { status: 500 })
  }
}
