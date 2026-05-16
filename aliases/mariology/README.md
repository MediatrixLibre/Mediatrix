# `mariology.pages.dev` — fourth 301 alias

A path-preserving redirect to `stella-maris.pages.dev`, matching the
existing alias pattern used by `mediatrix-marian-library.pages.dev` and
`mediatrixlibre.pages.dev`.

## Why this exists

- Single-word, search-friendly subdomain
- The library's primary identity stays at `stella-maris.pages.dev`
  (Stella Maris is the site's own ornament; SEO + GSC verification +
  Lighthouse 100/100/100/100 + auto-deploy are already settled there)
- This alias gives readers a shorter URL to share without touching the
  primary

## Deploy

Auth must be on the **Mediatrixdev** Cloudflare account
(`95d30883324e9658fb8239a2f84c24e6`), not the legacy aicoding47 account.

If wrangler is bound to the wrong account:

```sh
npx wrangler login  # select Mediatrixdev@proton.me
```

Then from `~/Desktop/Mediatrix/`:

```sh
npx wrangler pages project create mariology --production-branch=main
npx wrangler pages deploy aliases/mariology \
  --project-name=mariology \
  --branch=main \
  --commit-dirty=true
```

That uploads the single `_redirects` file. Verify:

```sh
curl -sIL https://mariology.pages.dev/ | head -5
curl -sIL https://mariology.pages.dev/rosary.html | head -8
```

Both should show `HTTP/2 301 location: https://stella-maris.pages.dev/...`
on the first hop, then `HTTP/2 200` after following.

## Files

- `_redirects` — one line, path-preserving 301 to stella-maris.pages.dev
- `README.md` — this file
