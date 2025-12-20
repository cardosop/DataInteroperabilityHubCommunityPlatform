import { useState, useEffect, useRef, RefObject } from 'react'
import { useIntersectionObserver } from '@/hooks/useIntersectionObserver'

export interface UseLazyImageOptions {
  /**
   * Image source URL
   */
  src: string
  /**
   * Placeholder image URL (shown while loading)
   */
  placeholder?: string
  /**
   * Root margin for Intersection Observer
   * @default '50px'
   */
  rootMargin?: string
  /**
   * Whether to enable lazy loading
   * @default true
   */
  enabled?: boolean
}

export interface UseLazyImageReturn {
  /**
   * Image source to use
   */
  imageSrc: string
  /**
   * Whether image is loading
   */
  isLoading: boolean
  /**
   * Whether image has loaded
   */
  isLoaded: boolean
  /**
   * Error state
   */
  error: Error | null
  /**
   * Ref to attach to img element
   */
  imgRef: RefObject<HTMLImageElement>
}

/**
 * Hook for lazy loading images with Intersection Observer
 */
export function useLazyImage({
  src,
  placeholder,
  rootMargin = '50px',
  enabled = true,
}: UseLazyImageOptions): UseLazyImageReturn {
  const [imageSrc, setImageSrc] = useState(placeholder || '')
  const [isLoading, setIsLoading] = useState(true)
  const [isLoaded, setIsLoaded] = useState(false)
  const [error, setError] = useState<Error | null>(null)
  const imgRef = useRef<HTMLImageElement>(null)

  // Use intersection observer to detect when image enters viewport
  const intersectionObserver = useIntersectionObserver({
    enabled,
    rootMargin,
    once: true, // Only load once
  })

  // Sync img ref with intersection observer ref
  useEffect(() => {
    if (imgRef.current && intersectionObserver.ref.current === null) {
      ;(intersectionObserver.ref as any).current = imgRef.current
    }
  }, [intersectionObserver.ref])

  const isIntersecting = intersectionObserver.isIntersecting

  // Load image when it enters viewport
  useEffect(() => {
    if (!enabled) {
      setImageSrc(src)
      setIsLoading(false)
      setIsLoaded(true)
      return
    }

    if (!isIntersecting) {
      return
    }

    // Start loading the image
    const imageLoader = new Image()
    imageLoader.src = src

    imageLoader.onload = () => {
      setImageSrc(src)
      setIsLoading(false)
      setIsLoaded(true)
    }

    imageLoader.onerror = () => {
      setError(new Error(`Failed to load image: ${src}`))
      setIsLoading(false)
    }
  }, [src, enabled, isIntersecting])

  return {
    imageSrc,
    isLoading,
    isLoaded,
    error,
    imgRef,
  }
}

