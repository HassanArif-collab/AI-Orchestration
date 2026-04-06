// apps/web/src/lib/dnd-compat.ts
//
// TEMPORARY COMPATIBILITY SHIM — Will be DELETED in Phase 3.
//
// The old Kanban components (Board, Card, Column) import from `@dnd-kit/core`.
// Phase 1 removed `@dnd-kit/core` in favor of `@dnd-kit/react` + `@dnd-kit/dom`.
// Phase 3 will completely rewrite the Kanban board using the new API.
//
// Until Phase 3, this shim provides the old API surface as no-op stubs
// so that TypeScript compiles without errors. The drag-and-drop behavior
// is non-functional until Phase 3.

// ─── Transform type (replaces @dnd-kit/utilities CSS.Transform) ─────────
export interface Transform {
  x: number;
  y: number;
  scaleX: number;
  scaleY: number;
}

// ─── DragStartEvent / DragEndEvent stubs ────────────────────────────────
export interface DragStartEvent {
  active: { id: string | number; data: { current?: Record<string, unknown> } };
}

export interface DragEndEvent {
  active: { id: string | number; data: { current?: Record<string, unknown> } };
  over: { id: string | number; data: { current?: Record<string, unknown> } } | null;
  canceled?: boolean;
}

// ─── Collision detection stubs ──────────────────────────────────────────
export const closestCenter = {
  collisionDetection: (() => () => null) as unknown,
};

// ─── DndContext component (no-op wrapper) ───────────────────────────────
export function DndContext({
  children,
  collisionDetection: _collisionDetection,
  onDragStart: _onDragStart,
  onDragEnd: _onDragEnd,
  onDragOver: _onDragOver,
}: {
  children: React.ReactNode;
  collisionDetection?: unknown;
  onDragStart?: (event: DragStartEvent) => void;
  onDragEnd?: (event: DragEndEvent) => void;
  onDragOver?: (event: unknown) => void;
}) {
  return <>{children}</>;
}

// ─── DragOverlay component (no-op wrapper) ─────────────────────────────
export function DragOverlay({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}

// ─── useDraggable hook (stub — no actual drag behavior) ─────────────────
export function useDraggable(_args: {
  id: string;
  data?: Record<string, unknown>;
}) {
  return {
    attributes: {} as Record<string, unknown>,
    listeners: {} as Record<string, unknown>,
    setNodeRef: () => {},
    transform: null as Transform | null,
    isDragging: false,
  };
}

// ─── useDroppable hook (stub — no actual drop behavior) ─────────────────
export function useDroppable(_args: {
  id: string;
  data?: Record<string, unknown>;
}) {
  return {
    setNodeRef: () => {},
    isOver: false,
  };
}
