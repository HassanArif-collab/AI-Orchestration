# Phase 6 Implementation Plan — Critical, High, and Medium Audit Fixes

**Branch:** `codebase-audit-finding-fixes`
**Date:** 2026-04-02

---

## Phase A — Critical Fixes (4 items)

### A1. Implement `useDraggable` on Kanban Cards
**File:** `src/components/kanban/Card.tsx`
- Import `useDraggable` from `@dnd-kit/core`
- Wrap the card's root `<div>` with the draggable ref and attributes
- Pass `id={card.id}` and `data={{ columnNumber: card.column }}` (for collision detection)
- Add visual feedback (`opacity-50`, `rotate-2`) when dragging
- Add a `DragOverlay` in `Board.tsx` to show a polished drag preview
- Requires: Card.tsx, Board.tsx, Column.tsx

### A2. Fix Duplicate Streaming Text in Chat
**Files:** `src/hooks/useChat.ts`, `src/components/chat/ChatPanel.tsx`
- In `useChat.ts`: Do NOT update the assistant message in the `messages` array during streaming (remove lines 121-127 in the `token` case)
- Only update `streamingText` state during streaming
- In the `done` event handler: set the final accumulated text on the assistant message
- `ChatPanel.tsx`: The streaming overlay (lines 188-196) renders `streamingText` — this stays

### A3. Fix cardHelpers Column 5 Review Handling
**File:** `src/lib/cardHelpers.ts`
- In the Column 5 block (line 91-106): add `status === 'review'` check
- When status is `review`, return action `review` with label `👀 Review Script`

### A4. Add Timeout to Chat SSE Connection
**File:** `src/hooks/useChat.ts`
- Create an AbortController with a 120-second timeout before the fetch
- Use `AbortSignal.any()` to combine timeout + user abort signals (fallback: manually abort timeout on response)
- If timeout fires, throw an error with message `API 408: SSE stream timed out` (matches errorMapper regex)

---

## Phase B — High Impact Fixes (5 items)

### B1. Install `@tailwindcss/typography` Plugin
**File:** `package.json`, `src/index.css`
- Add `@tailwindcss/typography` to devDependencies
- Run `npm install`
- Add `@plugin "@tailwindcss/typography"` to `src/index.css` (Tailwind v4 syntax)

### B2. Fix Score Unit Mismatch in PublishConfirmModal
**File:** `src/components/review/PublishConfirmModal.tsx`
- Change `{scriptPreview.score.toFixed(1)}/10` to `{scriptPreview.score}%`

### B3. Fix Card Border CSS Conflicts
**File:** `src/components/kanban/Card.tsx`
- Convert the 5 separate border expressions (lines 132-136) into a single mutually-exclusive ternary chain

### B4. Fix CardDrawer Escape Handler Leak
**File:** `src/components/kanban/CardDrawer.tsx`
- Add `if (!card) return;` guard at top of the escape useEffect
- Add `card` to the dependency array

### B5. Fix Agent Stream Race Condition
**File:** `src/hooks/useAgentStream.ts`
- Move subscription creation inside a `.then()` after `loadHistory()` resolves
- This ensures history is loaded before the INSERT subscription starts

---

## Phase C — Polish & Cleanup (4 items)

### C1. Migrate useYouTube to Use api.ts
**File:** `src/hooks/useYouTube.ts`
- Remove the local `fetcher` and `API_BASE`
- Import `api` from `../lib/api`
- Rewrite `useCompetitorVideos` to use `api.getCompetitorVideos()` via SWR
- Rewrite `useOwnAnalytics` to use `api.getOwnAnalytics()` via SWR
- Remove the local `repurposeVideo` function (already exists in api.ts)

### C2. Fix errorMapper Compatibility for Chat Errors
**File:** `src/hooks/useChat.ts`
- Change error format from `Chat API returned ${status}: ${body}` to `API ${status}: ${body}`

### C3. Fix StatusBadge Dark Theme Colors
**File:** `src/components/common/StatusBadge.tsx`
- Convert all light-mode color pairs to dark-mode variants
- e.g. `bg-blue-100 text-blue-800` to `bg-blue-900/50 text-blue-300`

### C4. Clean Up Dead Code and Unused Dependencies
**Files:** `package.json`, `src/lib/api.ts`, `src/lib/constants.ts`, `src/components/ui/ErrorCard.tsx`
- Remove `@dnd-kit/sortable`, `@dnd-kit/utilities`, `react-router-dom` from package.json
- Remove dead API methods: `getTasks`, `getStats` from api.ts
- Remove dead constants: `ACTIVE_STATUSES`, `ACTION_REQUIRED_STATUSES` from constants.ts
- Remove unused `ErrorCard` component
- Delete unused `tailwind.config.js`
- Remove redundant `autoprefixer` from postcss.config.js
- Update `index.html` title from "web" to "AI Content Factory"
