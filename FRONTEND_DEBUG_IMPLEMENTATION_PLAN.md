# Frontend Debug Implementation Plan
## AI-Orchestration Dashboard - HTML/CSS/JS Issues

**Branch:** codebase-audit-finding-fixes  
**Scope:** Static frontend only (HTML/CSS/JavaScript in `/workspace/apps/api/static/`)  
**Excluded:** React frontend (`/workspace/apps/web/`)

---

## Executive Summary

The dashboard has **15 critical issues** across 4 categories:
- **Missing Files**: 2 files referenced but don't exist
- **JavaScript Errors**: 6 runtime/logic errors
- **CSS Issues**: 3 styling problems
- **Backend Integration**: 4 API contract mismatches

---

## Issue Categories & Priority

### 🔴 CRITICAL (Blocks functionality)
1. Missing pipeline.js file
2. Kanban drawer display state bug
3. Chat session persistence data loss
4. SSE event handler timing issue

### 🟠 HIGH (Degrades user experience)
5. Toast action button styling incomplete
6. DLQ panel close function missing from global scope
7. Progress bar element references may fail
8. Expiry countdown only runs on kanban tab

### 🟡 MEDIUM (Minor bugs)
9. Memory session rendering assumes object structure
10. Analytics competitor data structure mismatch
11. Visual manifests error handling silent
12. Settings health check status mapping incorrect

### 🟢 LOW (Cosmetic/edge cases)
13. CSS responsive breakpoint cuts off nav labels abruptly
14. Thinking time calculation can show negative values
15. Extend button duplicate creation possible

---

## Detailed Issue Breakdown

### 1. ❌ MISSING FILE: pipeline.js Reference
**Location:** `index.html` line 83 (NOT PRESENT - documentation mentions it)  
**Expected:** `/workspace/apps/api/static/js/pipeline.js`  
**Actual:** File doesn't exist, functionality is in `kanban.js`  
**Impact:** Documentation mismatch, potential confusion  
**Fix:** Update DASHBOARD.md documentation to reference kanban.js instead

---

### 2. ❌ BUG: Kanban Drawer Display State
**Location:** `kanban.js` lines 358-359, 479-482  
**Issue:** Drawer uses both `classList.remove('hidden')` AND `style.display = ''`, but close only sets `display: none`  
**Symptom:** Drawer may not properly hide/show on subsequent opens  
**Code:**
```javascript
// openDrawer (line 358-359)
drawer.classList.remove('hidden');
drawer.style.display = '';

// closeDrawer (line 479-482)
drawer.classList.add('hidden');
drawer.style.display = 'none';
```
**Fix:** Consistently use classList only, remove inline style manipulation

---

### 3. ❌ BUG: Chat Session Data Loss
**Location:** `chat.js` lines 148-157  
**Issue:** `delSession` removes from localStorage but doesn't delete from backend LangGraph checkpointer  
**Symptom:** Deleted conversations can reappear if backend still has them  
**Code:**
```javascript
async function delSession(e, sid) {
  e.stopPropagation();
  if (!confirm('Delete this conversation from local history?')) return;
  _removeSession(sid);  // Only removes from localStorage
  // Missing: API call to delete from backend
}
```
**Fix:** Add API call to `/api/chat/conversations/{id}` DELETE endpoint if available, or update confirmation message

---

### 4. ❌ BUG: SSE Event Handler Timing
**Location:** `app.js` lines 484-495  
**Issue:** `connectSSE()` called with 100ms delay, but Kanban.handleSSEEvent may not be defined yet  
**Symptom:** Early SSE events lost, Kanban board doesn't update in real-time initially  
**Code:**
```javascript
window.addEventListener('load', () => {
  switchTab(_initTab);
  setTimeout(() => {
    connectSSE();  // Kanban module may not be initialized
    // ...
  }, 100);
});
```
**Fix:** Increase delay to 300ms OR check if Kanban is defined before connecting SSE

---

### 5. ⚠️ INCOMPLETE: Toast Action Button Styling
**Location:** `dashboard.css` lines 984-996  
**Issue:** `.toast-action` class defined but toast container doesn't apply proper spacing  
**Symptom:** Action buttons may overlap with toast text on long messages  
**Fix:** Add flexbox layout to toast container when action button present

---

### 6. ⚠️ SCOPE ISSUE: DLQ Panel Close Function
**Location:** `app.js` lines 403-407  
**Issue:** `closeDLQPanel()` defined but not exposed to window scope  
**Symptom:** HTML onclick handler `onclick="closeDLQPanel()"` may fail in strict mode  
**Code:**
```html
<!-- index.html line 70 -->
<button class="dlq-panel-close" onclick="closeDLQPanel()">✕</button>
```
**Fix:** Add `window.closeDLQPanel = closeDLQPanel;` at end of app.js

---

### 7. ⚠️ NULL REFERENCE: Progress Bar Elements
**Location:** `app.js` lines 188-190  
**Issue:** Progress event handlers reference elements that may not exist  
**Symptom:** Console errors when progress events fire before UI rendered  
**Code:**
```javascript
const bar = document.getElementById(`progress-bar-${runId}`);
const label = document.getElementById(`progress-label-${runId}`);
const batchLabel = document.getElementById(`batch-progress-label-${runId}`);
if (bar && d.progress_percent != null) {  // Only checks bar, not others
  bar.style.width = `${Math.min(100, d.progress_percent)}%`;
}
if (label && d.stage) {  // Could fail if label is null
  label.textContent = d.stage;
}
```
**Fix:** Add null checks for all three elements before accessing properties

---

### 8. ⚠️ LOGIC ERROR: Expiry Countdown Tab Check
**Location:** `kanban.js` lines 531-535  
**Issue:** Countdown only runs when kanban tab is active, but cards exist on page even when hidden  
**Symptom:** Expiry badges don't update if user switches tabs  
**Code:**
```javascript
_startExpiryCountdown() {
  this._expiryInterval = setInterval(() => {
    if (typeof _activeTab !== 'undefined' && _activeTab !== 'kanban') return;
    this._updateExpiryBadges();
  }, 30000);
}
```
**Fix:** Remove tab check OR update badges even when tab is inactive (more useful)

---

### 9. 📝 DATA ASSUMPTION: Memory Session Structure
**Location:** `memory.js` lines 32-42  
**Issue:** Code assumes sessions might be objects with metadata, but backend returns plain strings  
**Symptom:** Wasted computation checking for object properties that don't exist  
**Code:**
```javascript
const sid = typeof s === 'string' ? s : (s.session_id || s);
// ...
<div class="provider-name">${escHtml(sid)}</div>
<div class="provider-model">${typeof s === 'object' ? escHtml(s.metadata?.session_type||'—') : ''}</div>
```
**Fix:** Simplify to handle string-only response, remove object checks

---

### 10. 📝 API CONTRACT: Competitor Data Structure
**Location:** `analytics.js` lines 32-36  
**Issue:** Comment says backend returns `{videos: [...]}`, but code also checks `compData || []`  
**Symptom:** May fail silently if structure changes  
**Code:**
```javascript
const compData = await api('/api/analytics/competitors');
renderVidTable('comp-table', compData.videos || compData || []);
```
**Fix:** Add explicit error handling and log unexpected structures

---

### 11. 🤫 SILENT FAILURE: Visual Manifests Error Handling
**Location:** `visual.js` lines 18-26  
**Issue:** Empty catch block swallows all errors  
**Symptom:** No user feedback when manifest loading fails  
**Code:**
```javascript
try {
  const m = await api('/api/visual/manifests');
  // ...
} catch {}  // Silent failure
```
**Fix:** Show error message or at least console.log the error

---

### 12. 🔄 STATUS MAPPING: Settings Health Check
**Location:** `settings.js` lines 19-28  
**Issue:** Status dot logic doesn't handle all possible backend status values  
**Symptom:** Unknown statuses show wrong color  
**Code:**
```javascript
const dot = s.overall==='healthy'?'online':s.overall==='degraded'?'warning':'offline';
// Later:
${statusDot(v.status==='online'||v.status==='ok'?'online':v.status==='not_configured'||v.status==='not_scaffolded'?'unknown':'offline')}
```
**Fix:** Create comprehensive status mapping function

---

### 13. 📱 RESPONSIVE: Nav Label Cutoff
**Location:** `dashboard.css` lines 391-398  
**Issue:** At 768px breakpoint, nav labels disappear abruptly without transition  
**Symptom:** Jarring UX on resize  
**Code:**
```css
@media (max-width: 768px) {
  #app { grid-template-columns: 56px 1fr; }
  .nav-label, .badge, .sidebar-header h1, .sidebar-footer { display: none; }
  /* No transition applied */
}
```
**Fix:** Add CSS transitions for smoother responsive behavior

---

### 14. ⏱️ EDGE CASE: Negative Thinking Time
**Location:** `kanban.js` lines 234-242  
**Issue:** If `thinking_started_at` is in the future (clock skew), elapsed is negative  
**Symptom:** Shows negative time or NaN  
**Code:**
```javascript
const elapsed = task.thinking_started_at ? Math.floor((Date.now() - new Date(task.thinking_started_at).getTime()) / 1000) : null;
let timeText = '';
if (elapsed && elapsed > 10) {  // Doesn't handle negative
```
**Fix:** Add `Math.max(0, elapsed)` or check if elapsed < 0

---

### 15. 🔘 DUPLICATE: Extend Button Creation
**Location:** `kanban.js` lines 555-568  
**Issue:** `_updateExpiryBadges` checks for existing button but condition may fail  
**Symptom:** Multiple extend buttons on same card  
**Code:**
```javascript
const existingExtend = card.querySelector('.extend-btn');
if (expiryInfo.level === 'danger' || expiryInfo.level === 'expired') {
  if (!existingExtend) {
    // Creates new button
  }
}
```
**Fix:** Ensure querySelector works correctly by verifying class name consistency

---

## Testing Strategy

### Manual Testing Checklist
- [ ] Navigate through all 7 tabs without console errors
- [ ] Create a new Kanban task and verify SSE updates work
- [ ] Test chat conversation creation and deletion
- [ ] Verify DLQ panel opens and closes properly
- [ ] Test provider key saving flow
- [ ] Check memory session viewing
- [ ] Verify analytics data displays correctly
- [ ] Test settings health check shows accurate status
- [ ] Resize browser to test responsive breakpoints
- [ ] Leave Kanban tab open for 30+ minutes to test expiry countdown

### Automated Testing (Future)
- Set up Playwright/Cypress for E2E testing
- Add JavaScript unit tests with Jest
- Implement visual regression testing

---

## Implementation Order

### Phase 1: Critical Fixes (Day 1)
1. Fix Kanban drawer display state (#2)
2. Fix SSE event handler timing (#4)
3. Expose DLQ functions to window scope (#6)
4. Add null checks for progress bars (#7)

### Phase 2: High Priority (Day 2)
5. Fix chat session deletion (#3)
6. Improve toast action button layout (#5)
7. Fix expiry countdown logic (#8)
8. Update documentation for pipeline.js (#1)

### Phase 3: Medium Priority (Day 3)
9. Simplify memory session rendering (#9)
10. Add error handling for analytics (#10)
11. Add error logging for visual manifests (#11)
12. Fix settings status mapping (#12)

### Phase 4: Polish (Day 4)
13. Add CSS transitions for responsive (#13)
14. Fix thinking time edge case (#14)
15. Prevent duplicate extend buttons (#15)

---

## Success Criteria

✅ **Zero console errors** during normal operation  
✅ **All tabs load** without JavaScript errors  
✅ **SSE events** properly update UI in real-time  
✅ **Responsive design** works smoothly at all breakpoints  
✅ **User actions** (create, delete, approve) complete successfully  
✅ **Error states** are gracefully handled with user feedback  

---

## Notes

- All fixes maintain backward compatibility with existing backend APIs
- No breaking changes to public interfaces
- CSS changes are additive only (no removals)
- JavaScript fixes use defensive programming patterns
- Documentation will be updated alongside code changes

---

**Created:** Based on codebase audit of branch `codebase-audit-finding-fixes`  
**Total Estimated Effort:** 4 developer-days  
**Risk Level:** Low (isolated to static assets, no database migrations)
