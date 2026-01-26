'use client'

import { motion, AnimatePresence, useReducedMotion, type Variants, type HTMLMotionProps } from 'framer-motion'
import { forwardRef, type ReactNode } from 'react'

// ============= Animation Variants =============

export const fadeInVariants: Variants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { duration: 0.2, ease: 'easeOut' }
  },
  exit: {
    opacity: 0,
    transition: { duration: 0.15, ease: 'easeIn' }
  }
}

export const slideUpVariants: Variants = {
  hidden: { opacity: 0, y: 10 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.25, ease: [0.25, 0.46, 0.45, 0.94] }
  },
  exit: {
    opacity: 0,
    y: -10,
    transition: { duration: 0.2, ease: 'easeIn' }
  }
}

export const slideDownVariants: Variants = {
  hidden: { opacity: 0, y: -10 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.25, ease: [0.25, 0.46, 0.45, 0.94] }
  },
  exit: {
    opacity: 0,
    y: 10,
    transition: { duration: 0.2, ease: 'easeIn' }
  }
}

export const slideLeftVariants: Variants = {
  hidden: { opacity: 0, x: 20 },
  visible: {
    opacity: 1,
    x: 0,
    transition: { duration: 0.25, ease: [0.25, 0.46, 0.45, 0.94] }
  },
  exit: {
    opacity: 0,
    x: -20,
    transition: { duration: 0.2, ease: 'easeIn' }
  }
}

export const slideRightVariants: Variants = {
  hidden: { opacity: 0, x: -20 },
  visible: {
    opacity: 1,
    x: 0,
    transition: { duration: 0.25, ease: [0.25, 0.46, 0.45, 0.94] }
  },
  exit: {
    opacity: 0,
    x: 20,
    transition: { duration: 0.2, ease: 'easeIn' }
  }
}

export const scaleInVariants: Variants = {
  hidden: { opacity: 0, scale: 0.95 },
  visible: {
    opacity: 1,
    scale: 1,
    transition: { duration: 0.2, ease: [0.25, 0.46, 0.45, 0.94] }
  },
  exit: {
    opacity: 0,
    scale: 0.95,
    transition: { duration: 0.15, ease: 'easeIn' }
  }
}

export const collapseVariants: Variants = {
  hidden: {
    height: 0,
    opacity: 0,
    transition: { duration: 0.2, ease: 'easeIn' }
  },
  visible: {
    height: 'auto',
    opacity: 1,
    transition: { duration: 0.25, ease: [0.25, 0.46, 0.45, 0.94] }
  },
  exit: {
    height: 0,
    opacity: 0,
    transition: { duration: 0.2, ease: 'easeIn' }
  }
}

export const staggerContainerVariants: Variants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.05,
      delayChildren: 0.1
    }
  },
  exit: {
    opacity: 0,
    transition: {
      staggerChildren: 0.03,
      staggerDirection: -1
    }
  }
}

export const staggerItemVariants: Variants = {
  hidden: { opacity: 0, y: 10 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.2 }
  },
  exit: {
    opacity: 0,
    y: -10,
    transition: { duration: 0.15 }
  }
}

// ============= Animation Components =============

interface AnimationProps extends Omit<HTMLMotionProps<'div'>, 'variants'> {
  children: ReactNode
  className?: string
  delay?: number
}

export const FadeIn = forwardRef<HTMLDivElement, AnimationProps>(
  ({ children, className, delay = 0, ...props }, ref) => {
    const prefersReducedMotion = useReducedMotion()
    return (
      <motion.div
        ref={ref}
        initial="hidden"
        animate="visible"
        exit="exit"
        variants={prefersReducedMotion ? undefined : fadeInVariants}
        transition={{ delay, duration: prefersReducedMotion ? 0 : undefined }}
        className={className}
        {...props}
      >
        {children}
      </motion.div>
    )
  }
)
FadeIn.displayName = 'FadeIn'

export const SlideUp = forwardRef<HTMLDivElement, AnimationProps>(
  ({ children, className, delay = 0, ...props }, ref) => {
    const prefersReducedMotion = useReducedMotion()
    return (
      <motion.div
        ref={ref}
        initial="hidden"
        animate="visible"
        exit="exit"
        variants={prefersReducedMotion ? undefined : slideUpVariants}
        transition={{ delay, duration: prefersReducedMotion ? 0 : undefined }}
        className={className}
        {...props}
      >
        {children}
      </motion.div>
    )
  }
)
SlideUp.displayName = 'SlideUp'

export const SlideDown = forwardRef<HTMLDivElement, AnimationProps>(
  ({ children, className, delay = 0, ...props }, ref) => {
    const prefersReducedMotion = useReducedMotion()
    return (
      <motion.div
        ref={ref}
        initial="hidden"
        animate="visible"
        exit="exit"
        variants={prefersReducedMotion ? undefined : slideDownVariants}
        transition={{ delay, duration: prefersReducedMotion ? 0 : undefined }}
        className={className}
        {...props}
      >
        {children}
      </motion.div>
    )
  }
)
SlideDown.displayName = 'SlideDown'

export const SlideLeft = forwardRef<HTMLDivElement, AnimationProps>(
  ({ children, className, delay = 0, ...props }, ref) => {
    const prefersReducedMotion = useReducedMotion()
    return (
      <motion.div
        ref={ref}
        initial="hidden"
        animate="visible"
        exit="exit"
        variants={prefersReducedMotion ? undefined : slideLeftVariants}
        transition={{ delay, duration: prefersReducedMotion ? 0 : undefined }}
        className={className}
        {...props}
      >
        {children}
      </motion.div>
    )
  }
)
SlideLeft.displayName = 'SlideLeft'

export const SlideRight = forwardRef<HTMLDivElement, AnimationProps>(
  ({ children, className, delay = 0, ...props }, ref) => {
    const prefersReducedMotion = useReducedMotion()
    return (
      <motion.div
        ref={ref}
        initial="hidden"
        animate="visible"
        exit="exit"
        variants={prefersReducedMotion ? undefined : slideRightVariants}
        transition={{ delay, duration: prefersReducedMotion ? 0 : undefined }}
        className={className}
        {...props}
      >
        {children}
      </motion.div>
    )
  }
)
SlideRight.displayName = 'SlideRight'

export const ScaleIn = forwardRef<HTMLDivElement, AnimationProps>(
  ({ children, className, delay = 0, ...props }, ref) => {
    const prefersReducedMotion = useReducedMotion()
    return (
      <motion.div
        ref={ref}
        initial="hidden"
        animate="visible"
        exit="exit"
        variants={prefersReducedMotion ? undefined : scaleInVariants}
        transition={{ delay, duration: prefersReducedMotion ? 0 : undefined }}
        className={className}
        {...props}
      >
        {children}
      </motion.div>
    )
  }
)
ScaleIn.displayName = 'ScaleIn'

export const Collapse = forwardRef<HTMLDivElement, AnimationProps & { open?: boolean }>(
  ({ children, className, open = true, ...props }, ref) => {
    const prefersReducedMotion = useReducedMotion()
    return (
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            ref={ref}
            initial="hidden"
            animate="visible"
            exit="exit"
            variants={prefersReducedMotion ? undefined : collapseVariants}
            className={className}
            style={{ overflow: 'hidden' }}
            {...props}
          >
            {children}
          </motion.div>
        )}
      </AnimatePresence>
    )
  }
)
Collapse.displayName = 'Collapse'

interface StaggerContainerProps extends Omit<HTMLMotionProps<'div'>, 'variants'> {
  children: ReactNode
  className?: string
  staggerDelay?: number
}

export const StaggerContainer = forwardRef<HTMLDivElement, StaggerContainerProps>(
  ({ children, className, staggerDelay = 0.05, ...props }, ref) => {
    const prefersReducedMotion = useReducedMotion()
    return (
      <motion.div
        ref={ref}
        initial="hidden"
        animate="visible"
        exit="exit"
        variants={
          prefersReducedMotion
            ? undefined
            : {
                ...staggerContainerVariants,
                visible: {
                  opacity: 1,
                  transition: {
                    staggerChildren: staggerDelay,
                    delayChildren: 0.1,
                  },
                },
              }
        }
        className={className}
        {...props}
      >
        {children}
      </motion.div>
    )
  }
)
StaggerContainer.displayName = 'StaggerContainer'

export const StaggerItem = forwardRef<HTMLDivElement, AnimationProps>(
  ({ children, className, ...props }, ref) => {
    const prefersReducedMotion = useReducedMotion()
    return (
      <motion.div
        ref={ref}
        variants={prefersReducedMotion ? undefined : staggerItemVariants}
        className={className}
        {...props}
      >
        {children}
      </motion.div>
    )
  }
)
StaggerItem.displayName = 'StaggerItem'

// ============= Page Transition Wrapper =============

interface PageTransitionProps {
  children: ReactNode
  className?: string
}

export function PageTransition({ children, className }: PageTransitionProps) {
  const prefersReducedMotion = useReducedMotion()
  return (
    <motion.div
      initial={{ opacity: 0, y: prefersReducedMotion ? 0 : 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: prefersReducedMotion ? 0 : -8 }}
      transition={{ duration: prefersReducedMotion ? 0 : 0.3, ease: [0.25, 0.46, 0.45, 0.94] }}
      className={className}
    >
      {children}
    </motion.div>
  )
}

// ============= Presence Wrapper =============

interface PresenceProps {
  children: ReactNode
  show?: boolean
  mode?: 'sync' | 'wait' | 'popLayout'
}

export function Presence({ children, show = true, mode = 'sync' }: PresenceProps) {
  return (
    <AnimatePresence mode={mode}>
      {show && children}
    </AnimatePresence>
  )
}

// Re-export motion and AnimatePresence for direct use
export { motion, AnimatePresence }
