import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

/**
 * Tailwind class merge utility.
 * Combines clsx (conditional classes) with tailwind-merge (deduplication).
 *
 * Usage: cn("px-4 py-2", isActive && "bg-blue-500", className)
 *
 * NEVER use raw string concatenation or array.join for dynamic Tailwind classes.
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
