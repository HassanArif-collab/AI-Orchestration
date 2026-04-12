import type { KanbanCard } from '@/lib/schema';
import type { CardAction, CardActionInfo } from '@/types';

/**
 * Determines the appropriate action to display on a KanbanCard
 * based on its column_index, status, and metadata (e.g. expires_at).
 *
 * This replaces the scattered conditional checks that previously lived
 * inside Card.tsx and caused mismatches between frontend and backend state.
 *
 * NOTE: Uses `column_index` (matching DB schema), NOT `column`.
 */

export function getCardAction(card: KanbanCard): CardActionInfo {
  // Column 1: Topic Finding (read-only, backend is busy)
  if (card.column_index === 1) {
    return {
      action: 'none',
      reason: 'AI is discovering topics. Please wait.',
      label: '',
      variant: 'secondary',
    };
  }

  // Column 2: Suggested Topics
  if (card.column_index === 2) {
    // Has expiry time = temporary suggestion that needs saving
    if (card.expires_at) {
      const expiryTime = new Date(card.expires_at);
      const isExpired = expiryTime < new Date();

      if (isExpired) {
        return {
          action: 'none',
          reason: 'Topic has expired and will be removed.',
          label: '',
          variant: 'secondary',
        };
      }

      return {
        action: 'save',
        reason: 'Topic will expire soon. Save it to start production.',
        label: '💾 Save Topic',
        variant: 'warning',
      };
    }

    // Saved suggestion (no expires_at) = ready for production
    return {
      action: 'start_pipeline',
      reason: 'Ready to start production pipeline.',
      label: '🚀 Start Production',
      variant: 'success',
    };
  }

  // Column 3: Researching
  if (card.column_index === 3) {
    if (card.status === 'error') {
      return {
        action: 'resubmit',
        reason: 'Pipeline failed. Click to retry.',
        label: '🔄 Retry',
        variant: 'warning',
      };
    }
    return {
      action: 'none',
      reason: 'Pipeline is running. Check the drawer for progress.',
      label: '',
      variant: 'primary',
    };
  }

  // Column 4: Script Evolution / Writing
  if (card.column_index === 4) {
    if (card.status === 'error') {
      return {
        action: 'resubmit',
        reason: 'Script generation failed. Click to retry.',
        label: '🔄 Retry',
        variant: 'warning',
      };
    }
    return {
      action: 'none',
      reason: 'Script is being written. Check the drawer for progress.',
      label: '',
      variant: 'primary',
    };
  }

  // Column 5: Review + Visuals
  if (card.column_index === 5) {
    if (card.status === 'review_required' || card.status === 'review') {
      return {
        action: 'review',
        reason: 'Script is ready for your review and approval.',
        label: '👀 Review Script',
        variant: 'primary',
      };
    }
    if (card.status === 'error') {
      return {
        action: 'resubmit',
        reason: 'Visual annotation failed. Click to retry.',
        label: '🔄 Retry',
        variant: 'warning',
      };
    }
    return {
      action: 'none',
      reason: 'Waiting for visual annotations.',
      label: '',
      variant: 'secondary',
    };
  }

  // Column 6: Published (Notion)
  if (card.column_index === 6) {
    return {
      action: 'none',
      reason: 'Script published to Notion.',
      label: '',
      variant: 'secondary',
    };
  }

  return {
    action: 'none',
    reason: '',
    label: '',
    variant: 'secondary',
  };
}

// Re-export for backward compatibility
export type { CardAction, CardActionInfo };
