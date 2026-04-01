import type { KanbanCard } from '../types';

/**
 * Determines the appropriate action to display on a KanbanCard
 * based on its column, status, and metadata (e.g. expires_at).
 *
 * This replaces the scattered conditional checks that previously lived
 * inside Card.tsx and caused mismatches between frontend and backend state.
 */

export type CardAction = 'save' | 'start_pipeline' | 'resubmit' | 'review' | 'none';

export interface CardActionInfo {
  action: CardAction;
  reason: string;
  label: string;
  variant: 'primary' | 'secondary' | 'warning' | 'success';
}

export function getCardAction(card: KanbanCard): CardActionInfo {
  // Column 2: Suggested Topics
  if (card.column === 2) {
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

  // Column 3: In Production / Researching
  if (card.column === 3) {
    if (card.status === 'error') {
      return {
        action: 'resubmit',
        reason: 'Pipeline failed. Click to retry.',
        label: '🔄 Retry',
        variant: 'warning' as const,
      };
    }
    return {
      action: 'none',
      reason: 'Pipeline is running. Check the drawer for progress.',
      label: '',
      variant: 'primary',
    };
  }

  // Column 4: Script Evolution / Ready for Review
  if (card.column === 4) {
    if (card.status === 'error') {
      return {
        action: 'resubmit',
        reason: 'Script generation failed. Click to retry.',
        label: '🔄 Retry',
        variant: 'warning' as const,
      };
    }
    return {
      action: 'review',
      reason: 'Script is ready for your review.',
      label: '👀 Review Script',
      variant: 'primary',
    };
  }

  // Column 5: Review + Visuals
  if (card.column === 5) {
    if (card.status === 'review') {
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
        variant: 'warning' as const,
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
  if (card.column === 6) {
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
