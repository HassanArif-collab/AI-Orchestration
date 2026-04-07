// apps/web/src/lib/constants.ts
//
// Centralized configuration for all polling intervals, timeouts,
// retry policies, and optimization thresholds.
//
// Phase 8: All values that were previously scattered across multiple
// files are now in ONE place for easy tuning.

// ─── Card Expiration ───────────────────────────────────────────────────────

/** 3-hour expiration for Column 2 suggested topics (in ms) */
export const EXPIRATION_MS = 3 * 60 * 60 * 1000;

/** Warn the user when < 30 minutes remain before auto-expiry */
export const EXPIRY_WARN_MS = 30 * 60 * 1000;

// ─── API / Fetch ───────────────────────────────────────────────────────────

/** Default timeout for all API requests (in ms). AbortController fires after this. */
export const API_TIMEOUT_MS = 15_000;

/** SSE streaming timeout — abort hanging streams after 2 minutes */
export const SSE_TIMEOUT_MS = 120_000;

/** Maximum number of automatic retries on transient errors */
export const MAX_RETRIES = 2;

/** HTTP status codes eligible for automatic retry */
export const RETRYABLE_STATUS_CODES = [408, 429, 500, 502, 503, 504];

/** Exponential backoff delays for retries (in ms): 1s, 2s */
export const RETRY_DELAYS_MS = [1_000, 2_000];

// ─── Polling Intervals ─────────────────────────────────────────────────────

/** Pipeline state polling — while pipeline is actively running */
export const PIPELINE_POLL_MS = 5_000;

/** Provider quota polling — only when Quota tab is visible */
export const QUOTA_POLL_MS = 5_000;

/** Competitor videos refresh interval */
export const YOUTUBE_POLL_MS = 300_000; // 5 minutes

/** DLQ stats/items refresh */
export const DLQ_POLL_MS = 10_000; // 10 seconds

// ─── Toast System ──────────────────────────────────────────────────────────

/** Maximum concurrent toasts before oldest is dismissed */
export const MAX_TOASTS = 5;

/** Default auto-dismiss delay for toasts (in ms) */
export const TOAST_AUTO_DISMISS_MS = 5_000;

// ─── Virtual Scrolling Threshold ───────────────────────────────────────────

/** Minimum number of cards in a column before enabling virtualization */
export const VIRTUAL_SCROLL_THRESHOLD = 30;

/** Estimated card height for virtual scroll (in px) */
export const ESTIMATED_CARD_HEIGHT = 180;
