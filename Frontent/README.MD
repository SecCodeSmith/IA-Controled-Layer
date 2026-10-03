# Control Layer — dashboard & employee chat

Vite + React 18 + TypeScript (strict) frontend for the AI Control Layer. Implements the sign-in
screen, the employee chat, and the admin dashboard (live feed + attack suite, audit log, call
detail, policy, security reports) against the API contract in `WIKI/api-contract.md`.

## Stack

React 18, TypeScript (strict), react-router-dom v7 (data router), TanStack Query v5, Tailwind
CSS v4 (`@tailwindcss/vite`, no `tailwind.config.js` — tokens live in `src/index.css`), native
`EventSource` for SSE, Vitest + React Testing Library + MSW v2 for tests.

## Running it

```bash
npm ci            # first time: npm install
npm run dev       # http://localhost:5173
```

In dev mode the app talks to a mocked backend (MSW, `src/test/handlers.ts`) so the whole UI —
sign-in, chat, live feed with simulated SSE pushes, audit log, call detail, policy, attack suite,
reports — works stand-alone with no backend running. Mocking is wired in `src/main.tsx` and is
excluded from production builds (the `msw/browser` import is behind a dev-only dynamic import, so
it is tree-shaken out of `npm run build`'s output — verified: no `msw` references in `dist/`).

### Environment variables

| Variable | Default | Used for |
|---|---|---|
| `VITE_CONTROL_LAYER_URL` | `http://localhost:8080` | `/auth/*`, `/v1/*`, `/api/*` (control layer) |
| `VITE_AGENT_URL` | `http://localhost:8090` | `/agent/*` (demo agent service) |
| `VITE_ADMIN_TOKEN` | `admin-dev-token` | `X-Admin-Token` header on every `/api/*` call |

Set them in a `.env.local` (not committed) to point at a real backend once it is available; the
defaults match the contract's dev defaults so no `.env` file is required to run against a local
backend started with its own defaults.

## Scripts

- `npm run dev` — Vite dev server with MSW mocking enabled.
- `npm run build` — `tsc -b` (strict type-check) then `vite build`.
- `npm test -- --run` — Vitest + React Testing Library + MSW, one run (omit `-- --run` for watch mode).
- `npm run lint` — ESLint (flat config, typescript-eslint + react-hooks + react-refresh).

## Structure

```text
src/
  api/        fetch wrapper (client.ts) + one module per resource, each exporting TanStack Query hooks
  hooks/      useEventSource (generic SSE + reconnect), useFeedStream, useAttackRunStream
  types/      TypeScript types mirroring WIKI/api-contract.md
  lib/        small pure helpers (formatting, colors, session storage, role/region labels)
  context/    AuthContext (signed-in identity + token, persisted to localStorage)
  components/ layout, chat, feed, audit, policy, attack, common — grouped like the screens
  pages/      SignIn, Chat, LiveFeed, AuditLog, CallDetail, Policy, Reports
  test/       MSW handlers + fixtures (shared by dev-mode mocking and by the test suite),
              Vitest setup, render helper, EventSource mock for SSE tests
```

## Known deviations from the brief (and why)

- **React Router v7** (data router, `createBrowserRouter`) instead of v6: the brief allows either;
  v6 currently has an open-redirect advisory with no v6 patch, only fixed in v7.18.4, so v7 was
  used to keep `npm audit` clean.
- **SSE admin auth**: native `EventSource` cannot set custom headers, so the two admin SSE endpoints
  (`/api/feed/stream`, `/api/attack-suite/runs/{id}/stream`) are called with the admin token as a
  `?admin_token=` query parameter instead of the `X-Admin-Token` header the contract specifies for
  `/api/*`. Every other `/api/*` call still uses the header. The same query-param convention is used
  for the audit/alerts export links, since clicking a plain link can't set a header either.
- **Policy rule "points"**: the brief's Policy screen description asks for "id, action, points and
  OWASP refs" per rule; the contract's `Rule` shape has no numeric `points` field, only `severity`.
  The rules list renders `severity` (when present) in that slot instead of inventing a points value.
- **Tool sidebar scope labels**: the employee-chat mockup hardcodes per-server scope text (e.g.
  "Jira → read · write"). The sidebar instead derives each MCP server's aggregate scope
  (`read` / `read · write` / `read · write*`) from the actual tool tags in `/v1/me`, so it stays
  correct for every demo user instead of repeating one mockup's invented example.
- **Audit log list screen**: only the call-detail screen was mocked up; the list page (filters +
  table + links to `/admin/audit/:callId`) was designed to match the Live Feed table's visual
  language since no dedicated mockup exists for it.
- **MSW v2 → v3**: `msw` resolved to v3 by default; pinned to the latest `2.x` (`2.15.0`) since the
  brief specifies MSW v2.
