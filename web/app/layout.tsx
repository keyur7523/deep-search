import type React from "react"
import { Inter, JetBrains_Mono } from "next/font/google"
import { ErrorBoundary } from "@/components/error-boundary"
import "./globals.css"

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
})

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-jetbrains-mono",
})

export const metadata = {
  title: "Deep Research - Multi-Agent Research Platform",
  description: "AI-powered research platform for comprehensive topic exploration",
  generator: 'keyurdev',
  icons: {
    icon: '/placeholder-logo.svg',
  },
}

export const viewport = {
  themeColor: '#7c3aed',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className={`${inter.variable} ${jetbrainsMono.variable}`}>
      <body>
        <ErrorBoundary>{children}</ErrorBoundary>
      </body>
    </html>
  )
}
