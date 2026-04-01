/**
 * Maps raw API errors into user-friendly error objects.
 * Used across review, chat, and card components for consistent error display.
 *
 * Error format from api.ts: `API {status}: {body}`
 * Uses regex to match the status prefix, avoiding false positives from
 * substring matching (e.g., "Error processing 404-byte payload").
 */

interface FriendlyError {
  title: string;
  message: string;
  action?: string;
}

// Matches `API <status_code>:` at the start of the error message
const API_STATUS_REGEX = /^API (\d{3}):/;

export function mapApiError(err: unknown): FriendlyError {
  const msg = err instanceof Error ? err.message : String(err);

  // Network errors
  if (msg.includes('NetworkError') || msg.includes('fetch') || msg.includes('Failed to fetch')) {
    return {
      title: 'Connection error',
      message: 'Could not reach the server. Check your connection and try again.',
      action: 'Retry',
    };
  }

  // Timeout errors (from AbortController)
  if (err instanceof DOMException && err.name === 'AbortError') {
    return {
      title: 'Request timed out',
      message: 'The server took too long to respond. Please try again.',
      action: 'Retry',
    };
  }

  // Extract HTTP status code from the standard API error format
  const statusMatch = msg.match(API_STATUS_REGEX);
  if (statusMatch) {
    const statusCode = statusMatch[1];

    switch (statusCode) {
      case '503':
        return {
          title: 'Service temporarily unavailable',
          message: 'The pipeline service is restarting. Please wait 10 seconds and try again.',
          action: 'Retry',
        };
      case '404':
        return {
          title: 'Resource not found',
          message: 'The requested resource no longer exists. Please refresh the page.',
          action: 'Refresh',
        };
      case '500':
        return {
          title: 'Server error',
          message: 'An internal server error occurred. Your decision was not saved.',
          action: 'Retry',
        };
      case '401':
      case '403':
        return {
          title: 'Authentication required',
          message: 'Please check your API credentials in Settings.',
          action: 'Open Settings',
        };
      case '429':
        return {
          title: 'Rate limited',
          message: 'Too many requests. Please wait a moment and try again.',
          action: 'Retry',
        };
      case '400':
        return {
          title: 'Bad request',
          message: 'The request was rejected by the server. Please check your input and try again.',
          action: 'Retry',
        };
      default:
        return {
          title: `Request failed (${statusCode})`,
          message: msg.replace(API_STATUS_REGEX, '').trim() || 'An unexpected error occurred.',
          action: 'Retry',
        };
    }
  }

  // Generic fallback
  return {
    title: 'Something went wrong',
    message: msg || 'An unexpected error occurred. Please try again.',
    action: 'Retry',
  };
}
