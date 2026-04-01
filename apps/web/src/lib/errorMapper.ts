/**
 * Maps raw API errors into user-friendly error objects.
 * Used across review, chat, and card components for consistent error display.
 */

interface FriendlyError {
  title: string;
  message: string;
  action?: string;
}

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

  // HTTP status codes
  if (msg.includes('503')) {
    return {
      title: 'Service temporarily unavailable',
      message: 'The pipeline service is restarting. Please wait 10 seconds and try again.',
      action: 'Retry',
    };
  }

  if (msg.includes('404')) {
    return {
      title: 'Card not found',
      message: 'This card no longer exists. Please refresh the page.',
      action: 'Refresh',
    };
  }

  if (msg.includes('500')) {
    return {
      title: 'Server error',
      message: 'An internal server error occurred. Your decision was not saved.',
      action: 'Retry',
    };
  }

  if (msg.includes('401') || msg.includes('403')) {
    return {
      title: 'Authentication required',
      message: 'Please check your API credentials in Settings.',
      action: 'Open Settings',
    };
  }

  if (msg.includes('429')) {
    return {
      title: 'Rate limited',
      message: 'Too many requests. Please wait a moment and try again.',
      action: 'Retry',
    };
  }

  if (msg.includes('400')) {
    return {
      title: 'Bad request',
      message: 'The request was rejected by the server. Please try again.',
      action: 'Retry',
    };
  }

  // Generic fallback
  return {
    title: 'Something went wrong',
    message: msg || 'An unexpected error occurred. Please try again.',
    action: 'Retry',
  };
}
