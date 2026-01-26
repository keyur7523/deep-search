'use client'

import { SkeletonTopicForm } from '@/components/ui/skeletons'
import { motion } from 'framer-motion'

export default function Loading() {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="min-h-screen flex items-center justify-center p-4"
    >
      <SkeletonTopicForm />
    </motion.div>
  )
}
