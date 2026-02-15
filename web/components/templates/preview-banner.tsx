import Link from 'next/link'
import { Eye } from 'lucide-react'

export function PreviewBanner() {
  return (
    <div className="bg-amber-500 text-amber-950 px-4 py-2 text-center text-sm font-medium flex items-center justify-center gap-2">
      <Eye className="w-4 h-4" />
      <span>Preview Mode — You are viewing draft content</span>
      <Link
        href="/api/exit-preview"
        className="underline underline-offset-2 hover:no-underline ml-2"
      >
        Exit Preview
      </Link>
    </div>
  )
}
