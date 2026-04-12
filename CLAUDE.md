Source Code Reference
Source code for dependencies is available in opensrc/ for deeper understanding of implementation details.

See opensrc/sources.json for the list of available packages and their versions.

Use this source code when you need to understand how a package works internally, not just its types/interface.

Fetching Additional Source Code
To fetch source code for a package or repository you need to understand, run:

npx opensrc <package>           # npm package (e.g., npx opensrc zod)
npx opensrc pypi:<package>      # Python package (e.g., npx opensrc pypi:requests)
npx opensrc crates:<package>    # Rust crate (e.g., npx opensrc crates:serde)
npx opensrc <owner>/<repo>      # GitHub repo (e.g., npx opensrc vercel/ai)

---

## Documentation & API Reference

### Library Documentation (Context7)
Always use **Context7** when you need up-to-date documentation, code examples, or configuration steps for libraries.

**Rule:** Always use Context7 when needing library/API documentation, code generation, setup, or configuration steps without me having to explicitly ask.

To search for documentation:
- `npx ctx7 library <name> <query>`: Search for a library by name and task (e.g., `npx ctx7 library supabase auth`)
- `npx ctx7 docs <libraryId> <query>`: Fetch specific documentation (e.g., `npx ctx7 docs /vercel/next.js middleware`)

Use the `/library/id` syntax in prompts to target specific libraries directly.

