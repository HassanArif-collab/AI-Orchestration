---
name: ctx7-docs
description: Fetch up-to-date documentation and code examples for any library using Context7.
---

# Context7 - Up-to-date Code Docs

Use this skill when you need library/API documentation, code generation, setup, or configuration steps.

### Commands

#### 1. Resolve Library ID
If you don't know the exact `libraryId` (e.g., `/vercel/next.js`), use this to find it.
```bash
npx ctx7 library <libraryName> <query>
```
*   **libraryName**: The name of the library (e.g., `supabase`).
*   **query**: The task you are trying to perform (e.g., `authentication`).

#### 2. Query Documentation
Once you have the `libraryId`, fetch relevant documentation for your task.
```bash
npx ctx7 docs <libraryId> <query>
```
*   **libraryId**: Context7 library ID (e.g., `/supabase/auth`).
*   **query**: Your specific question or task.

### Best Practices
- **Prefer Slash Syntax**: If you already know the library ID, use it directly (e.g., `use library /mongodb/docs for this`).
- **Specify Versions**: Mention versions (e.g., `Next.js 14`) in the query to get precise results.
- **Deep Context**: If documentation isn't enough, use `opensrc` to fetch implementation details.
