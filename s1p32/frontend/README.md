# S1P32 quality analysis

An interactive dashboard for S1P32 quality analysis. It reads a folder of published JSON files and shows key numbers, charts, findings, recommendations, a what-if tool, a forecast, a prediction form, an explorer and a plain-English guide.

## Run it locally

You need Node 22 or newer.

    npm install
    npm run check
    npm run dev

Open http://localhost:5173. Every feature works locally with no account or login, including the /api and /mcp routes. `npm run check` copies the latest data into `public/data` and validates every file against the shapes the pages expect, so problems show up in the terminal instead of as empty panels. `npm run dev:worker` runs the production runtime and security headers locally at http://localhost:8787.

Local settings go in `.dev.vars` (see `.dev.vars.example`). To try the MCP route locally, set `MCP_MODE=open` there and run:

    curl -X POST http://localhost:5173/mcp -H "content-type: application/json" -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'

Remote assistants cannot reach localhost, so connecting one requires the published address.

## Update after the data is refreshed

Run `npm run deploy` in this folder. It refreshes the data, checks it, builds and publishes.

## Publish

    npx wrangler login
    npm run deploy

Wrangler prints the live address. Use `npx wrangler login` only the first time.

## Protecting the site

The data files are public to anyone who can open the site. For real client data, put the address behind a Cloudflare Access policy. Synthetic data can stay open.

## Optional MCP access

The site can expose a read-only MCP endpoint at /mcp. It is controlled by `MCP_MODE` in `wrangler.toml`:

- `off` (default): the endpoint answers 404.
- `token`: callers must send `Authorization: Bearer <token>`. Set the token with `npx wrangler secret put MCP_TOKEN`.
- `open`: no token. Suitable for synthetic data only.

## Where the data comes from

The `public/data` folder is a copy of the analysis output folder and is refreshed by `npm run check`, `npm run dev` and `npm run build`. The check reads every file with the same adapters the pages use and reports OK, UNAVAILABLE (skipped), MISSING or INVALID per file, then runs a test prediction.

## Folder map

- `src/` pages, components, hooks and utilities
- `src/utils/adapters.js` turns each data file into the shape the pages use
- `worker/index.js` the /api/forecast and /mcp routes
- `scripts/` data refresh and data check
- `public/` static files and the data copy
