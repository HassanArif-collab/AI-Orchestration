import { useState, useEffect } from 'react';
import { differenceInSeconds, parseISO } from 'date-fns';
import { EXPIRATION_MS } from '../lib/constants';

interface TimerResult {
  remainingMinutes: number;   // Minutes left (for display)
  remainingSeconds: number;   // Total seconds left (for precision)
  isExpired: boolean;          // True when time's up
  percentage: number;          // 0-100, how much time has passed (for progress bar)
}

/**
 * Calculates countdown for a card's 3-hour expiration timer.
 * Only meaningful for Column 2 (Suggested Topics) cards.
 *
 * Updates every 30 seconds to avoid unnecessary re-renders.
 * (We don't need per-second precision for a 3-hour window.)
 */
export function useCardTimer(expiresAt: string | null): TimerResult {
  const [now, setNow] = useState(Date.now());

  useEffect(() => {
    if (!expiresAt) return;
    const interval = setInterval(() => setNow(Date.now()), 30_000); // every 30s
    return () => clearInterval(interval);
  }, [expiresAt]);

  if (!expiresAt) {
    return { remainingMinutes: Infinity, remainingSeconds: Infinity, isExpired: false, percentage: 0 };
  }

  const expiry = parseISO(expiresAt).getTime();
  const totalSeconds = EXPIRATION_MS / 1000;
  const secondsLeft = Math.max(0, differenceInSeconds(expiry, now));
  const minutesLeft = Math.ceil(secondsLeft / 60);
  const percentage = Math.min(100, ((totalSeconds - secondsLeft) / totalSeconds) * 100);

  return {
    remainingMinutes: minutesLeft,
    remainingSeconds: secondsLeft,
    isExpired: secondsLeft <= 0,
    percentage,
  };
}
