# Phase 5 Implementation Plan — Remaining UX & Accessibility Fixes

**Branch:** `codebase-audit-finding-fixes`
**Date:** 2026-04-02
**Scope:** 13 remaining deferred issues from the comprehensive React frontend audit
**Status:** IN PROGRESS

---

## Overview

Phases 1–4 addressed 38 issues across the React frontend (`apps/web/src/`). This phase
addresses the final 13 deferred items, completing the audit remediation.

---

## Group A: Accessibility & Keyboard Navigation (5 issues)

### A1 — Focus trap + ARIA for CardDrawer (M8)
**File:** `apps/web/src/components/kanban/CardDrawer.tsx`
**Issue:** The drawer has no `role="dialog"`, `aria-modal`, or focus trap. Keyboard users can Tab
into background content while the drawer is open.
**Approach:** Add ARIA attributes to the drawer container. Implement a lightweight focus trap
using `useRef` + `useEffect` that intercepts Tab/Shift+Tab and cycles focus between the first
and last focusable elements within the drawer.

### A2 — Escape handler + Focus trap for PublishConfirmModal (M9)
**File:** `apps/web/src/components/review/PublishConfirmModal.tsx`
**Issue:** No Escape key handler, no ARIA dialog attributes, no focus trap. The modal can only be
dismissed by clicking the backdrop or the "Keep Editing" button.
**Approach:** Add `useEffect` for Escape key → `onCancel()`. Add `role="dialog"` and
`aria-modal="true"`. Share the focus trap utility from A1.

### A3 — WAI-ARIA Tab pattern for Sidebar (L10/M11)
**File:** `apps/web/src/layout/Sidebar.tsx`
**Issue:** Sidebar tabs are plain `<button>` elements with no ARIA roles or arrow-key navigation.
Screen reader users can Tab through linearly but cannot use Left/Right arrows.
**Approach:** Add `role="tablist"` on container, `role="tab"` + `aria-selected` on each button,
`role="tabpanel"` on the content area. Add `onKeyDown` handler for ArrowLeft/ArrowRight navigation.

### A4 — Toast exit animation (L12)
**Files:** `apps/web/src/hooks/useToast.ts`, `apps/web/src/components/ui/ToastContainer.tsx`
**Issue:** Toasts appear with `animate-slide-in-right` but disappear instantly — no exit
animation. The `dismissToast` function immediately removes the toast from the array.
**Approach:** Add `status: 'active' | 'dismissing'` to the Toast type. `dismissToast` first sets
status to `'dismissing'` (triggering a CSS exit class), then removes after 300ms. Add
`animate-slide-out-right` keyframe to `index.css`.

### A5 — ScriptViewer responsive grid (M3)
**File:** `apps/web/src/components/review/ScriptViewer.tsx`
**Issue:** Uses `grid-cols-2` without responsive breakpoints. On small viewports or narrow drawers,
columns are too cramped.
**Approach:** Change to `grid-cols-1 lg:grid-cols-2` — single column on small screens, two
columns on large.

---

## Group B: Robustness & Bug Fixes (4 issues)

### B1 — Card.tsx review click propagation (L3)
**File:** `apps/web/src/components/kanban/Card.tsx`
**Issue:** The `'review'` case in `handleActionClick` calls `onClick()` directly, then the event
bubbles to the parent `<div onClick={onClick}>`, firing `onClick()` twice.
**Approach:** Call `e.stopPropagation()` at the top of `handleActionClick` for all cases, not
just non-review ones.

### B2 — Board.tsx setTimeout leak (L5)
**File:** `apps/web/src/components/kanban/Board.tsx`
**Issue:** Two `setTimeout` calls (drag error clear at 3s, optimistic revert at 3s) are not stored
in refs or cleaned up on unmount. Can cause stale state updates.
**Approach:** Store both timers in a `useRef<ReturnType<typeof setTimeout>[]>`, clear all in a
`useEffect` cleanup function.

### B3 — useAgentStream duplicate thoughts on reconnect (L7)
**File:** `apps/web/src/hooks/useAgentStream.ts`
**Issue:** On reconnect, history is reloaded (async) and a new subscription is created. If a
thought is inserted during the gap, it could appear twice. Intermediate channels are also leaked.
**Approach:** (a) Remove old channel before reconnecting. (b) Track a `Set<string>` of seen
thought IDs via `useRef`. In the INSERT callback, skip any thought whose ID is already in the
set. (c) Initialize the set from the history load response.

### B4 — supabase.ts placeholder client (L9)
**File:** `apps/web/src/lib/supabase.ts`
**Issue:** When `VITE_SUPABASE_URL` / `VITE_SUPABASE_ANON_KEY` are missing, a non-functional
Supabase client is created with fake credentials, causing confusing errors later.
**Approach:** Export `supabase` as `SupabaseClient | null`. Export an `isSupabaseConfigured()`
helper. Components that need Supabase check this before using the client. The placeholder URL
and key become `null` instead of fake values.

---

## Group C: Data & Layout (4 issues)

### C1 — QuotaPanel hardcoded RPM/TPM (L8)
**File:** `apps/web/src/components/telemetry/QuotaPanel.tsx`
**Issue:** Progress bars use hardcoded denominators (`rpm_remaining / 30`, `tpm_remaining / 500000`)
that don't match actual provider limits. Footer text claims "No hardcoded estimates."
**Approach:** Change progress bars to display raw remaining values without misleading percentage
bars. Show "30 RPM" and "500K TPM" as-is. Update footer to remove the misleading claim.

### C2 — Column hardcoded max-height (L4)
**File:** `apps/web/src/components/kanban/Column.tsx`
**Issue:** `max-h-[calc(100vh-180px)]` is a magic number that breaks if the header or column
header height changes.
**Approach:** Remove the `max-h-[calc(100vh-180px)]` entirely. The parent Column is already in a
flex column (`flex flex-col`) with `flex-1 overflow-y-auto` on the card list. The flex layout
will naturally constrain the height. If needed, add `min-h-0` to ensure flex shrinking works.

### C3 — MainLayout mobile responsive (M12)
**File:** `apps/web/src/layout/MainLayout.tsx`
**Issue:** The sidebar (384px) always renders inline via flex. On mobile (<768px), it consumes
nearly the entire viewport. The board columns require horizontal scroll.
**Approach:** Start sidebar collapsed on small screens by reading the initial `isOpen` state from
a media query or window width. Add a responsive class so the board can expand on mobile. The
existing `isOpen` toggle already collapses to `w-0`.

### C4 — MainLayout + Sidebar: initial collapsed state on mobile
**Files:** `apps/web/src/layout/MainLayout.tsx`, `apps/web/src/layout/Sidebar.tsx`
**Issue:** Sidebar defaults to `isOpen=true` which is wrong on mobile.
**Approach:** In `Sidebar.tsx`, initialize `isOpen` to `false` when `window.innerWidth < 1024`.
Accept an `initialOpen` prop from MainLayout so the parent controls this.

---

## Implementation Order

1. **useToast.ts + ToastContainer.tsx + index.css** (A4) — Foundation for toast exit animation
2. **useAgentStream.ts** (B3) — Robustness fix
3. **Board.tsx** (B2) — Robustness fix
4. **Card.tsx** (B1) — Quick bug fix
5. **Column.tsx** (C2) — Quick layout fix
6. **ScriptViewer.tsx** (A5) — Quick responsive fix
7. **QuotaPanel.tsx** (C1) — Data display fix
8. **supabase.ts** (B4) — Config safety
9. **CardDrawer.tsx** (A1) — Focus trap + ARIA
10. **PublishConfirmModal.tsx** (A2) — Focus trap + Escape + ARIA
11. **Sidebar.tsx** (A3) — ARIA tabs + keyboard nav
12. **MainLayout.tsx + Sidebar.tsx** (C3/C4) — Mobile responsive

---

## Files Changed (Estimated)

| File | Change Type |
|------|-------------|
| `hooks/useToast.ts` | Modify — add dismissing state |
| `components/ui/ToastContainer.tsx` | Modify — exit animation class |
| `index.css` | Modify — add slide-out-right keyframe |
| `hooks/useAgentStream.ts` | Modify — dedup + channel cleanup |
| `components/kanban/Board.tsx` | Modify — setTimeout cleanup |
| `components/kanban/Card.tsx` | Modify — stopPropagation |
| `components/kanban/Column.tsx` | Modify — remove magic max-h |
| `components/review/ScriptViewer.tsx` | Modify — responsive grid |
| `components/telemetry/QuotaPanel.tsx` | Modify — raw values instead of bars |
| `lib/supabase.ts` | Modify — null client on missing creds |
| `components/kanban/CardDrawer.tsx` | Modify — focus trap + ARIA |
| `components/review/PublishConfirmModal.tsx` | Modify — Escape + focus trap + ARIA |
| `layout/Sidebar.tsx` | Modify — ARIA tabs + keyboard + mobile initial |
| `layout/MainLayout.tsx` | Modify — mobile-aware sidebar |

**Total: 14 files modified, 0 new files**
