import { useState, useEffect } from 'react';
import { differenceInSeconds, parseISO } from 'date-fns';
import { EXPIRATION_MS } from '../lib/constants';

export interface TimerState {
  remainingMinutes: number;
  remainingSeconds: number;
  isExpired: boolean;
  percentage: number;
  isCritical: boolean;   // < 15 minutes — urgent orange
  isWarning: boolean;    // < 30 minutes — caution yellow
  timeString: string;    // Human-readable: "2h 30m", "15m", "45s"
}

/**
 * Calculates countdown for a card's 3-hour expiration timer.
 * Only meaningful for Column 2 (Suggested Topics) cards.
 *
 * Updates every 5 seconds for smooth countdown display.
 * Provides tiered urgency flags (warning < 30m, critical < 15m).
 */
export function useCardTimer(expiresAt: string | null): TimerState {
  const [now, setNow] = useState(Date.now());

  useEffect(() => {
    if (!expiresAt) return;
    const interval = setInterval(() => setNow(Date.now()), 5000);
    return () => clearInterval(interval);
  }, [expiresAt]);

  if (!expiresAt) {
    return {
      remainingMinutes: 0,
      remainingSeconds: 0,
      isExpired: false,
      isCritical: false,
      isWarning: false,
      timeString: '',
      percentage: 0,
    };
  }

  const expiry = parseISO(expiresAt).getTime();
  const totalSeconds = EXPIRATION_MS / 1000;
  const secondsLeft = Math.max(0, differenceInSeconds(expiry, now));

  if (secondsLeft <= 0) {
    return {
      remainingMinutes: 0,
      remainingSeconds: 0,
      isExpired: true,
      isCritical: false,
      isWarning: false,
      timeString: 'Expired',
      percentage: 100,
    };
  }

  const totalMinutes = Math.floor(secondsLeft / 60);
  const secs = secondsLeft % 60;
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;

  let timeString = '';
  if (hours > 0) {
    timeString = `${hours}h ${minutes}m`;
  } else if (minutes > 0) {
    timeString = `${minutes}m`;
  } else {
    timeString = `${secs}s`;
  }

  const percentage = Math.min(100, ((totalSeconds - secondsLeft) / totalSeconds) * 100);

  return {
    remainingMinutes: totalMinutes,
    remainingSeconds: secondsLeft,
    isExpired: false,
    isCritical: totalMinutes < 15,
    isWarning: totalMinutes >= 15 && totalMinutes < 30,
    timeString,
    percentage,
  };
}
