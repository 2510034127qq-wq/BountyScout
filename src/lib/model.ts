import { format } from 'date-fns';

/**
 * Computes a relative date string.
 * Fixed rounding boundary to ensure consistent behavior for 'today' and 'yesterday'.
 */
export function relativeDate(now: number, then: number): string {
  const diffInMs = now - then;
  const diffInDays = Math.floor(diffInMs / 86400000);

  if (diffInDays < 0) {
    return 'today';
  }
  if (diffInDays === 0) {
    return 'today';
  }
  if (diffInDays === 1) {
    return 'yesterday';
  }
  
  return `${diffInDays} days ago`;
}
