# Single-serving site host on Cloudflare Workers

A pattern for hosting a pile of one-off static pages — explainers, dashboards,
throwaway demos, "here's a link" pages — behind one custom domain, with
**push-to-deploy** and an optional **authenticated POST endpoint** for posting a
page without a commit.

The whole thing is one Worker plus a `public/` directory. No build step, no
framework, no database for the static case. Free tier is plenty.

```
git push  ──post-push hook──▶  wrangler deploy  ──▶  https://pages.example.com
   │                                                        │
   ├─ public/*.html  ── served as static assets ────────────┤
   └─ src/index.ts   ── Worker: index page, routing, auth ───┘
```

Two ways a page gets online:

| Path | How it's added | Where it lives | Shows in index |
|---|---|---|---|
| **Static** | commit `public/foo.html`, push | Git + Workers Assets | only if listed in `STATIC_PAGES` |
| **Dynamic** | `POST /` with an auth token | Workers KV | yes, automatically |

Use static for anything you want in version control. Use dynamic for "generate a
page and give me a URL right now" from a script or an agent.

---

## 1. Layout

```
your-site/
├── src/
│   ├── index.ts        Worker: routing, index page, auth, KV read/write
│   └── index.test.ts   tests (optional but cheap)
├── public/             static HTML pages + assets, served as-is
│   ├── foo.html
│   └── bar.html
├── bin/
│   ├── post            CLI: POST an HTML file to the dynamic endpoint
│   └── delete          CLI: DELETE a dynamic page
├── .githooks/
│   └── post-push       deploy on every push
├── wrangler.toml
├── package.json
└── .env.local.example  credential template (real .env.local is gitignored)
```

---

## 2. wrangler.toml

```toml
name = "your-site"
main = "src/index.ts"
compatibility_date = "2025-01-01"
compatibility_flags = ["nodejs_compat"]

workers_dev = true

# Custom domain(s). Each must be a zone you control in this Cloudflare account.
routes = [
  { pattern = "pages.example.com", custom_domain = true },
]

# Everything in ./public is served as a static asset.
[assets]
directory = "./public"
binding = "ASSETS"

# KV namespace backing the dynamic (POST) pages. Omit this whole block if you
# only ever want committed static pages.
# Create with: wrangler kv namespace create PAGES
[[kv_namespaces]]
binding = "PAGES"
id = "REPLACE_WITH_YOUR_KV_NAMESPACE_ID"
preview_id = "REPLACE_WITH_YOUR_PREVIEW_KV_NAMESPACE_ID"
```

`run_worker_first` (under `[assets]`) lets the Worker intercept matching paths
before the static asset layer — useful if you want to gate a subtree behind auth.
Skip it for the simple case where the Worker only handles `/` and unknown slugs.

---

## 3. The Worker

A trimmed, generic version of the routing core. It does four things: render the
index at `/`, serve a dynamic KV page or fall through to a static asset for
`/slug`, accept an authenticated `POST /` to create a page, and accept an
authenticated `DELETE /slug` to remove one.

```ts
interface Env {
  PAGES: KVNamespace;   // dynamic pages; omit if static-only
  ASSETS: Fetcher;      // bound to ./public by wrangler
  AUTH_TOKEN: string;   // secret; gates POST/DELETE
}

interface PageEntry {
  slug: string;
  title: string;
  createdAt: string;    // ISO 8601
  pinned?: boolean;
}

// Committed pages you want listed on the index, newest first after pinned ones.
// Files in public/ that are NOT listed here are still served at /<name> —
// they just don't appear in the index.
const STATIC_PAGES: PageEntry[] = [
  { slug: 'foo', title: 'Foo — a worked example', createdAt: '2026-01-02T00:00:00Z' },
  { slug: 'bar', title: 'Bar — another page',      createdAt: '2026-01-01T00:00:00Z' },
];

function sortEntries(entries: PageEntry[]): PageEntry[] {
  return [...entries].sort((a, b) => {
    if (a.pinned && !b.pinned) return -1;
    if (!a.pinned && b.pinned) return 1;
    return Date.parse(b.createdAt || '') - Date.parse(a.createdAt || '');
  });
}

function renderIndex(entries: PageEntry[]): string {
  const rows = entries
    .map(e => `<li><a href="/${e.slug}">${e.title}</a></li>`)
    .join('\n');
  return `<!DOCTYPE html><html><head><meta charset="utf-8">
<title>pages.example.com</title></head>
<body><h1>pages</h1><ul>${rows}</ul></body></html>`;
}

// Bearer-token gate. Single-user: one shared secret is enough. Set it with:
//   wrangler secret put AUTH_TOKEN
function requireAuth(request: Request, env: Env): Response | null {
  const auth = request.headers.get('Authorization');
  if (auth === `Bearer ${env.AUTH_TOKEN}`) return null;
  return new Response('Unauthorized', { status: 401 });
}

function makeSlug(title: string): string {
  return title
    .toLowerCase()
    .replace(/[^a-z0-9\s-]/g, '')
    .trim()
    .replace(/\s+/g, '-')
    .replace(/-+/g, '-')
    .slice(0, 50) || crypto.randomUUID().slice(0, 6);
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    const path = url.pathname;
    const slug = path.slice(1);

    // Index: static pages + any dynamic ones from KV, sorted.
    if (request.method === 'GET' && path === '/') {
      const dynamicRaw = await env.PAGES.get('_index');
      const dynamic: PageEntry[] = dynamicRaw ? JSON.parse(dynamicRaw) : [];
      const staticSlugs = new Set(STATIC_PAGES.map(p => p.slug));
      const merged = [...STATIC_PAGES, ...dynamic.filter(e => !staticSlugs.has(e.slug))];
      return new Response(renderIndex(sortEntries(merged)), {
        headers: { 'Content-Type': 'text/html; charset=UTF-8' },
      });
    }

    // Create a dynamic page: POST / with the HTML body and an X-Page-Title header.
    if (request.method === 'POST' && path === '/') {
      const authError = requireAuth(request, env);
      if (authError) return authError;
      const html = await request.text();
      if (!html.trim()) return new Response('Empty body', { status: 400 });
      const title = (request.headers.get('X-Page-Title') || 'Untitled').trim();
      const newSlug = makeSlug(title);
      const createdAt = new Date().toISOString();
      await env.PAGES.put(newSlug, JSON.stringify({ html, title, createdAt }));
      const idxRaw = await env.PAGES.get('_index');
      const idx: PageEntry[] = idxRaw ? JSON.parse(idxRaw) : [];
      const pageUrl = `${url.origin}/${newSlug}`;
      await env.PAGES.put('_index', JSON.stringify([
        { slug: newSlug, title, createdAt },
        ...idx.filter(e => e.slug !== newSlug),
      ]));
      return new Response(pageUrl + '\n', { headers: { 'X-URL': pageUrl } });
    }

    // Delete a dynamic page.
    if (request.method === 'DELETE' && slug) {
      const authError = requireAuth(request, env);
      if (authError) return authError;
      await env.PAGES.delete(slug);
      const idxRaw = await env.PAGES.get('_index');
      const idx: PageEntry[] = idxRaw ? JSON.parse(idxRaw) : [];
      await env.PAGES.put('_index', JSON.stringify(idx.filter(e => e.slug !== slug)));
      return new Response('Deleted\n');
    }

    // GET /slug: try KV first, then fall through to the static asset.
    if (request.method === 'GET' && slug) {
      const raw = await env.PAGES.get(slug);
      if (raw) {
        const { html } = JSON.parse(raw) as { html: string };
        return new Response(html, {
          headers: { 'Content-Type': 'text/html; charset=UTF-8' },
        });
      }
      return env.ASSETS.fetch(request); // serves public/<slug>.html if present
    }

    return new Response('Not found', { status: 404 });
  },
};
```

The split that makes this work: **static pages are git-controlled and listed in
code; dynamic pages live in KV and self-register in an `_index` key.** The index
merges both. Static wins on slug collision.

---

## 4. Push-to-deploy hook

A `post-push` hook runs `wrangler deploy` after every successful `git push`, so
the live site always matches `main`. Install it by pointing git at your hooks dir
once:

```bash
git config core.hooksPath .githooks
chmod +x .githooks/post-push
```

> Note: `post-push` is **not** a built-in git hook. Either invoke it from a
> wrapper/alias around `git push`, or use a real built-in like `pre-push`. The
> script below is the deploy step; wire it to whichever trigger you prefer.

```bash
#!/usr/bin/env bash
# Deploy to Cloudflare. Reads creds from the macOS Keychain, falling back to
# .env.local. Never commit real credentials — .env.local is gitignored.
set -e
cd "$(git rev-parse --show-toplevel)"

CF_KEY=$(security find-generic-password -s "cloudflare-global-api-key" -a "you@example.com" -w 2>/dev/null || true)
if [ -n "$CF_KEY" ]; then
  export CLOUDFLARE_API_KEY="$CF_KEY"
  export CLOUDFLARE_EMAIL="you@example.com"
  export CLOUDFLARE_ACCOUNT_ID="REPLACE_WITH_YOUR_ACCOUNT_ID"
elif [ -f .env.local ]; then
  set -a && . .env.local && set +a
else
  echo "✗ no Cloudflare credentials (keychain or .env.local)" >&2
  exit 1
fi

echo "→ deploying to Cloudflare..."
npx wrangler deploy
echo "✓ deployed: https://pages.example.com"
```

`.env.local.example` (commit this; the real `.env.local` stays gitignored):

```bash
CLOUDFLARE_API_TOKEN=
CLOUDFLARE_ACCOUNT_ID=
```

On Linux/CI, drop the Keychain branch and rely on the `.env.local` fallback or
real environment variables. A scoped **API token** (Workers Scripts: Edit) is
preferable to the global API key.

---

## 5. Posting a page without a commit

Two tiny CLIs make the dynamic path ergonomic. They read the auth token from the
Keychain so it never sits in shell history.

`bin/post`:

```bash
#!/usr/bin/env bash
# Usage: bin/post "Page Title" path/to/file.html
#        echo '<h1>hi</h1>' | bin/post "Page Title"
TOKEN=$(security find-generic-password -s "site-auth-token" -a "you" -w 2>/dev/null)
[ -z "$TOKEN" ] && { echo "set token: security add-generic-password -s site-auth-token -a you -w <token>"; exit 1; }
[ -z "$1" ] && { echo "Usage: $0 \"Title\" [file.html]"; exit 1; }

curl -s -X POST https://pages.example.com/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Page-Title: $1" \
  --data-binary "${2:+@$2}${2:-@-}"
```

`bin/delete`:

```bash
#!/usr/bin/env bash
# Usage: bin/delete <slug>
TOKEN=$(security find-generic-password -s "site-auth-token" -a "you" -w 2>/dev/null)
curl -s -X DELETE "https://pages.example.com/$1" -H "Authorization: Bearer $TOKEN"
```

The Worker's `AUTH_TOKEN` secret and the value you store in the Keychain must
match. Set the secret with `wrangler secret put AUTH_TOKEN`.

---

## 6. Adding a static page

1. Drop an HTML file in `public/` (e.g. `public/foo.html`).
2. Add an entry to `STATIC_PAGES` in `src/index.ts` if you want it indexed.
3. `git push` — the hook deploys it. Live at `https://pages.example.com/foo`.

Unlisted files in `public/` are still served; they just don't appear on the index
page. Good for assets (images, CSS) and "unlisted" links.

---

## 7. Tests (optional)

The Cloudflare Vitest pool runs Worker code in a real `workerd` runtime, so you
can assert on routing and the index without deploying:

```json
// package.json
{
  "scripts": {
    "deploy": "wrangler deploy",
    "dev": "wrangler dev",
    "test": "vitest run"
  },
  "devDependencies": {
    "@cloudflare/vitest-pool-workers": "^0.5.0",
    "@cloudflare/workers-types": "^4.0.0",
    "typescript": "^5.0.0",
    "vitest": "^2.1.0",
    "wrangler": "^4.0.0"
  }
}
```

Worth testing: index sort order (pinned first, then newest), and that the
auth gate actually rejects an unauthenticated `POST`/`DELETE`.

---

## Why this shape

- **One Worker, no framework.** Static HTML is the unit. Nothing to build.
- **Free tier covers it.** Workers + KV free limits are generous for personal use.
- **Two write paths, one index.** Git for permanence, KV + a token for "right now."
- **Push = deploy.** The live site is whatever's on `main`; no separate release step.

It scales down to "I want a URL for this HTML file" and up to a few dozen pages
on one domain before you'd want anything more structured.
