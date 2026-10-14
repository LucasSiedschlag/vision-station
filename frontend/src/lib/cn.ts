import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

/** Joins class names and lets the later Tailwind class win over the earlier one. */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
