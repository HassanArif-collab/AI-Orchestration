// Status values that indicate the card is actively processing
export const ACTIVE_STATUSES = new Set([
  'discovering', 'grading', 'researching', 'drafting',
  'scoring', 'mutating', 'visuals', 'publishing',
]);

// Status values that require human action
export const ACTION_REQUIRED_STATUSES = new Set([
  'suggested', 'review',
]);

// 3-hour expiration in milliseconds
export const EXPIRATION_MS = 3 * 60 * 60 * 1000;

// Poll interval for non-realtime data (quota, pipeline state)
export const POLL_INTERVAL_MS = 5000; // 5 seconds
