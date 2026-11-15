#!/usr/bin/env python3
# Builds the React dashboard into <project>/frontend/ from <project>/backend/output/.
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

# ============ USER SETTINGS: the only line you ever edit ============
BASE_DIR = r"C:\Users\you\content\s1p32"   # the same value used for the backend
# ===================================================================

FILES = {}

DOMAIN_STYLES = [
    (("retail", "store"), "#d97706", "#0f172a", "DM Sans", "Inter"),
    (("ecommerce", "e-commerce", "shop"), "#7c3aed", "#111827", "Plus Jakarta Sans", "Inter"),
    (("restaurant", "food"), "#b45309", "#3b0764", "Playfair Display", "Lato"),
    (("clinic", "health"), "#0d9488", "#0f4c81", "IBM Plex Sans", "IBM Plex Sans"),
    (("logistics", "freight", "transport"), "#16a34a", "#1c1917", "Roboto Mono", "Roboto"),
    (("warehouse", "fulfilment", "fulfillment"), "#0284c7", "#172033", "Barlow", "Inter"),
    (("saas", "subscription"), "#4f46e5", "#0b1220", "Manrope", "Inter"),
    (("salon", "beauty"), "#be185d", "#1a0a0f", "Cormorant Garamond", "Nunito"),
]
NEUTRAL_STYLE = ("#2563eb", "#0f172a", "Inter", "Inter")

# registry fallbacks, mirrored from src/utils/datasets.js
FALLBACKS = {
    "summary": ("meta", "summary", "meta/summary.json"),
    "run_log": ("meta", "run_log", "meta/run_log.json"),
    "kpis": ("understand", "kpis", "understand/kpis.json"),
    "charts": ("understand", "charts", "understand/charts.json"),
    "segments": ("understand", "segments", "understand/segments.json"),
    "anomalies": ("understand", "anomalies", "understand/anomalies.json"),
    "explorer": ("understand", "explorer", "understand/explorer.json"),
    "insights": ("decide", "insights", "decide/insights.json"),
    "recommendations": ("decide", "recommendations", "decide/recommendations.json"),
    "simulations": ("decide", "simulations", "decide/simulations/index.json"),
    "goals": ("decide", "goals", "decide/goals.json"),
    "forecast": ("monitor", "forecast", "monitor/forecast.json"),
    "forecast_lookup": ("monitor", "forecast_lookup", "monitor/forecast_lookup.json"),
    "scorer": ("monitor", "scorer", "monitor/scorer.json"),
    "goal_progress": ("monitor", "goal_progress", "monitor/goal_progress.json"),
    "alerts": ("monitor", "alerts", "monitor/alerts.json"),
}

VOCAB_BLACKLIST = [r"claude", r"anthropic", r"chatgpt", r"openai", r"\bllm\b", r"as an ai", r"\bskill\b"]


def die(msg):
    print("\nERROR: " + msg)
    sys.exit(1)


def read_json(path):
    try:
        with open(path, "r", encoding="utf-8-sig") as fh:
            return json.load(fh)
    except Exception as exc:  # reported by the caller
        return {"__read_error__": str(exc)}


def _lin(c):
    c = c / 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def lum(h):
    r, g, b = (int(h[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def contrast(a, b):
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def mix(h, other, t):
    a = [int(h[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(other[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join("%02x" % round(x + (y - x) * t) for x, y in zip(a, b))


def on_color(h):
    return max(("#ffffff", "#0f172a"), key=lambda c: contrast(c, h))


def accent_pair(accent):
    light = accent
    while contrast(on_color(light), light) < 4.5:
        light = mix(light, "#000000", 0.08)
    dark = mix(accent, "#ffffff", 0.3)
    while contrast(on_color(dark), dark) < 4.5:
        dark = mix(dark, "#ffffff", 0.08)
    return light, on_color(light), dark, on_color(dark)


def render(text, tokens):
    for key, value in tokens.items():
        text = text.replace(key, value)
    return text

FILES["package.json"] = r"""{
  "name": "__CLIENT_ID__",
  "private": true,
  "version": "1.0.0",
  "type": "module",
  "engines": { "node": ">=22" },
  "scripts": {
    "predev": "node scripts/refresh-data.mjs",
    "dev": "vite",
    "prebuild": "node scripts/refresh-data.mjs && node scripts/check-data.mjs",
    "build": "vite build",
    "check": "node scripts/refresh-data.mjs && node scripts/check-data.mjs",
    "preview": "vite preview",
    "dev:worker": "npm run build && wrangler dev",
    "deploy": "npm run build && wrangler deploy"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "recharts": "^2.15.0"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.3.0",
    "vite": "^5.4.0",
    "wrangler": "^4.0.0"
  }
}
"""

FILES["vite.config.js"] = r"""import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import fs from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

// Settings the worker reads in production come from wrangler.toml [vars] and, locally, from an optional .dev.vars file.
function readVars(root) {
  const vars = { MCP_MODE: 'off' };
  try {
    const toml = fs.readFileSync(path.join(root, 'wrangler.toml'), 'utf8');
    const section = toml.split(/^\[vars\]\s*$/m)[1];
    if (section) {
      for (const line of section.split('\n')) {
        if (/^\s*\[/.test(line)) break;
        const m = line.match(/^\s*([A-Z_][A-Z0-9_]*)\s*=\s*"([^"]*)"/);
        if (m) vars[m[1]] = m[2];
      }
    }
  } catch { /* no wrangler.toml: keep the defaults */ }
  try {
    const dev = fs.readFileSync(path.join(root, '.dev.vars'), 'utf8');
    for (const line of dev.split('\n')) {
      const m = line.match(/^\s*([A-Z_][A-Z0-9_]*)\s*=\s*(.*?)\s*$/);
      if (m) vars[m[1]] = m[2].replace(/^["']|["']$/g, '');
    }
  } catch { /* optional file */ }
  return vars;
}

// Stands in for the static-asset binding: serves files from public/ (the data folder lives there)
function localAssets(root) {
  const base = path.resolve(root, 'public') + path.sep;
  return {
    async fetch(request) {
      const rel = decodeURIComponent(new URL(request.url).pathname).replace(/^\/+/, '');
      const file = path.resolve(root, 'public', rel);
      if (!file.startsWith(base) || !fs.existsSync(file) || !fs.statSync(file).isFile()) {
        return new Response('Not found', { status: 404 });
      }
      const type = file.endsWith('.json') ? 'application/json' : 'application/octet-stream';
      return new Response(fs.readFileSync(file), { headers: { 'content-type': type } });
    },
  };
}

function ownedRoute(pathname) {
  return pathname.startsWith('/api/') || pathname === '/mcp' || pathname.startsWith('/mcp/');
}

// Runs worker/index.js for /api and /mcp while developing or previewing, so nothing needs an account
function localWorker() {
  const handler = loadWorker => async (req, res, next) => {
    const pathname = (req.url || '').split('?')[0];
    if (!ownedRoute(pathname)) return next();
    try {
      const worker = await loadWorker();
      const root = process.cwd();
      const chunks = [];
      for await (const chunk of req) chunks.push(chunk);
      const hasBody = chunks.length > 0 && req.method !== 'GET' && req.method !== 'HEAD';
      const request = new Request('http://' + (req.headers.host || 'localhost') + req.url, {
        method: req.method,
        headers: req.headers,
        body: hasBody ? Buffer.concat(chunks) : undefined,
      });
      const response = await worker.fetch(request, { ...readVars(root), ASSETS: localAssets(root) });
      res.statusCode = response.status;
      response.headers.forEach((value, key) => res.setHeader(key, value));
      res.end(Buffer.from(await response.arrayBuffer()));
    } catch (err) {
      res.statusCode = 500;
      res.setHeader('content-type', 'application/json');
      res.end(JSON.stringify({ error: 'The local worker failed: ' + (err && err.message) }));
    }
  };
  return {
    name: 'local-worker',
    configureServer(server) {
      server.middlewares.use(handler(async () => (await server.ssrLoadModule('/worker/index.js')).default));
    },
    configurePreviewServer(server) {
      const file = pathToFileURL(path.resolve(process.cwd(), 'worker/index.js')).href;
      server.middlewares.use(handler(async () => (await import(file)).default));
    },
  };
}

export default defineConfig({
  plugins: [react(), localWorker()],
  build: {
    outDir: 'dist',
    chunkSizeWarningLimit: 900,
    rollupOptions: {
      output: { manualChunks: { vendor: ['react', 'react-dom'], charts: ['recharts'] } },
    },
  },
  server: { port: 5173 },
});
"""

FILES["wrangler.toml"] = r"""name = "__WORKER_NAME__"
main = "worker/index.js"
compatibility_date = "__COMPAT_DATE__"

[assets]
directory = "./dist"
binding = "ASSETS"
not_found_handling = "single-page-application"
run_worker_first = ["/api/*", "/mcp", "/mcp/*"]

[vars]
MCP_MODE = "off"
"""

FILES["index.html"] = r"""<!doctype html>
<html lang="en" data-theme="light">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>__PROJECT_NAME_HTML__</title>
    <link rel="icon" type="image/svg+xml" href="/favicon.svg" />
__FONT_LINK__
    <script src="/theme-init.js"></script>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
"""

FILES["public/theme-init.js"] = r"""(function () {
  var theme = 'light';
  try {
    var saved = localStorage.getItem('theme');
    if (saved === 'dark' || saved === 'light') theme = saved;
    else if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) theme = 'dark';
  } catch (e) { /* storage blocked: fall back to the system setting below */
    if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) theme = 'dark';
  }
  document.documentElement.setAttribute('data-theme', theme);
})();
"""

FILES["public/_headers"] = r"""/*
  X-Content-Type-Options: nosniff
  X-Frame-Options: DENY
  Referrer-Policy: no-referrer
  Permissions-Policy: camera=(), microphone=(), geolocation=()
  Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'
/data/*
  Cache-Control: no-cache
"""

FILES["public/favicon.svg"] = r"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="14" fill="__ACCENT__"/><text x="32" y="43" text-anchor="middle" font-family="Arial, sans-serif" font-size="34" font-weight="700" fill="__ON_ACCENT__">__LETTER__</text></svg>
"""

FILES[".gitignore"] = r"""node_modules/
dist/
.wrangler/
.dev.vars
.env.local
"""

FILES[".dev.vars.example"] = r"""# Local settings for the /mcp route. Copy this file to .dev.vars to use them.
# MCP_MODE=open
# MCP_TOKEN=choose-a-long-random-value
"""

FILES["README.md"] = r"""# __PROJECT_NAME_MD__

An interactive dashboard for __PROJECT_NAME_MD__. It reads a folder of published JSON files and shows key numbers, charts, findings, recommendations, a what-if tool, a forecast, a prediction form, an explorer and a plain-English guide.

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
"""

FILES["scripts/refresh-data.mjs"] = r"""import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const frontendRoot = path.resolve(here, '..');
const source = path.resolve(frontendRoot, '..', 'backend', 'output');
const target = path.resolve(frontendRoot, 'public', 'data');
const norm = p => p.split(path.sep).join('/');

function countFiles(dir) {
  let n = 0;
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    n += entry.isDirectory() ? countFiles(path.join(dir, entry.name)) : 1;
  }
  return n;
}

function stamp(dir) {
  try {
    const c = JSON.parse(fs.readFileSync(path.join(dir, 'frontend_contract.json'), 'utf8').replace(/^\uFEFF/, ''));
    return c.generated_at || 'unknown';
  } catch {
    return 'unknown';
  }
}

if (fs.existsSync(source)) {
  if (!norm(target).endsWith('frontend/public/data')) {
    console.error('Refusing to replace an unexpected folder: ' + target);
    process.exit(1);
  }
  fs.rmSync(target, { recursive: true, force: true });
  fs.cpSync(source, target, { recursive: true });
  console.log('Data refreshed: ' + countFiles(target) + ' files, generated ' + stamp(target));
} else if (fs.existsSync(path.join(target, 'frontend_contract.json'))) {
  console.log('Using the existing data copy (generated ' + stamp(target) + ')');
} else {
  console.error('No data found.');
  console.error('Run main.py and then export_for_frontend.py in the backend folder, then try again.');
  process.exit(1);
}
"""

FILES["scripts/check-data.mjs"] = r"""import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { DATASETS, resolveDatasetPath } from '../src/utils/datasets.js';
import { adaptContract } from '../src/utils/adapters.js';
import { predict, defaultsFor, predictMode } from '../src/utils/predict.js';

const here = path.dirname(fileURLToPath(import.meta.url));
const dataDir = path.resolve(here, '..', 'public', 'data');
const CORE = ['kpis', 'charts', 'insights'];
let failed = false;

function readJson(file) {
  const text = fs.readFileSync(file, 'utf8').replace(/^\uFEFF/, '');
  return JSON.parse(text);
}

function walk(dir) {
  const out = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) out.push(...walk(full));
    else out.push(full);
  }
  return out;
}

const contractFile = path.join(dataDir, 'frontend_contract.json');
let contract = null;
try {
  contract = adaptContract(readJson(contractFile));
  console.log('OK           contract (schema version ' + contract.schemaVersion + ')');
} catch (err) {
  console.log('INVALID      contract: ' + (err && err.message));
  failed = true;
}

const loaded = {};
for (const [name, def] of Object.entries(DATASETS)) {
  const rel = resolveDatasetPath(contract, def);
  const file = path.join(dataDir, rel.replace(/^\/data\//, ''));
  if (!fs.existsSync(file)) {
    console.log('MISSING      ' + name + ' (' + rel + ')');
    loaded[name] = { data: null, error: { message: 'file is missing' } };
    if (CORE.includes(name)) failed = true;
    continue;
  }
  let raw;
  try {
    raw = readJson(file);
  } catch {
    console.log('INVALID      ' + name + ': not valid JSON');
    loaded[name] = { data: null, error: { message: 'invalid JSON' } };
    failed = true;
    continue;
  }
  if (raw && typeof raw === 'object' && !Array.isArray(raw) && raw.status === 'skipped') {
    console.log('UNAVAILABLE  ' + name + ' (skipped: ' + (raw.reason || 'no reason given') + ')');
    loaded[name] = { data: null, error: { message: 'skipped: ' + (raw.reason || 'no reason given') } };
    if (CORE.includes(name)) failed = true;
    continue;
  }
  try {
    const data = def.adapt(raw);
    loaded[name] = { data, error: null };
    console.log('OK           ' + name);
  } catch (err) {
    console.log('INVALID      ' + name + ': ' + (err && err.message));
    loaded[name] = { data: null, error: { message: (err && err.message) || 'invalid' } };
    failed = true;
  }
}

if (loaded.scorer && loaded.scorer.data) {
  try {
    const scorer = loaded.scorer.data;
    const out = predict(scorer, defaultsFor(scorer.fields));
    const bad = !Number.isFinite(out.value) || (scorer.task === 'classification' && (out.value < 0 || out.value > 100));
    if (bad) {
      console.log('INVALID      scorer: the test prediction returned ' + out.value);
      failed = true;
    } else {
      console.log('OK           scorer test prediction: ' + out.value.toFixed(2));
    }
    const base = defaultsFor(scorer.fields);
    for (const f of scorer.fields) {
      const tries = f.type === 'number' ? [f.min, f.max].filter(v => v !== null) : f.options;
      for (const v of tries) {
        const r = predict(scorer, { ...base, [f.key]: v });
        if (!Number.isFinite(r.value)) { console.log('INVALID      scorer: ' + f.key + ' = ' + v + ' gives ' + r.value); failed = true; }
      }
    }
    if (scorer.fidelity && scorer.fidelity.quality === 'low') console.log('WARNING      the scorer matches the real model only roughly');
  } catch (err) {
    console.log('INVALID      scorer test prediction failed: ' + (err && err.message));
    failed = true;
  }
}

const noScorer = { data: null, error: null };
console.log('Predict page mode: ' + predictMode(loaded.scorer || noScorer, loaded.forecastLookup || noScorer, loaded.forecast || noScorer));

const personal = /(^|_)(email|e_mail|phone|mobile|full_?name)(_|$)/i;
function scan(value, file, trail) {
  if (Array.isArray(value)) {
    value.slice(0, 50).forEach(v => scan(v, file, trail));
  } else if (value && typeof value === 'object') {
    for (const [k, v] of Object.entries(value)) {
      if (personal.test(k)) console.log('WARNING      ' + file + ' has a field named ' + k + ' (it will not be shown)');
      scan(v, file, trail);
    }
  }
}
const pathPattern = /[A-Za-z]:\\{1,2}(Users|Windows|Program)|\/Users\/|\/home\//;
for (const file of walk(dataDir).filter(f => f.endsWith('.json'))) {
  const text = fs.readFileSync(file, 'utf8');
  const rel = path.relative(dataDir, file).split(path.sep).join('/');
  if (pathPattern.test(text)) {
    console.log('INVALID      ' + rel + ' contains a local file path');
    failed = true;
  }
  try { scan(JSON.parse(text.replace(/^\uFEFF/, '')), rel, ''); } catch { /* already reported above */ }
}

if (failed) {
  console.log('\nData check failed. Fix the files marked INVALID or MISSING above.');
  process.exit(1);
}
console.log('\nData check passed.');
"""
FILES["worker/index.js"] = r"""const MCP_PROTOCOLS = ['2025-11-25', '2025-06-18', '2025-03-26'];
const SERVER_INFO = { name: '__WORKER_NAME__-analytics', version: '1.0.0' };
const MAX_CHARS = 60000;

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    try {
      if (url.pathname.startsWith('/api/')) return await handleApi(request, env, url);
      if (url.pathname === '/mcp' || url.pathname.startsWith('/mcp/')) return await handleMcp(request, env, url);
    } catch (err) {
      console.error('worker error', err && err.message);
      return json({ error: 'Unexpected server error' }, 500);
    }
    return env.ASSETS.fetch(request);
  },
};

function json(body, status = 200, extra = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      'Content-Type': 'application/json; charset=utf-8',
      'Cache-Control': 'no-store',
      'X-Content-Type-Options': 'nosniff',
      ...extra,
    },
  });
}

async function readAsset(env, url, path) {
  const res = await env.ASSETS.fetch(new Request(new URL(path, url.origin).toString()));
  if (!res.ok) return null;
  const type = res.headers.get('content-type') || '';
  if (type.includes('text/html')) return null;
  try { return await res.json(); } catch { return null; }
}

async function loadContract(env, url) {
  return (await readAsset(env, url, '/data/frontend_contract.json')) || {};
}

function contractPath(contract, outcome, key, fallback) {
  const rel = contract && contract.outcomes && contract.outcomes[outcome] && contract.outcomes[outcome][key];
  const chosen = typeof rel === 'string' && rel.endsWith('.json') && !rel.includes('..') ? rel : fallback;
  return '/data/' + chosen.replace(/^\/+/, '');
}

function sameOrigin(request, url) {
  const origin = request.headers.get('Origin');
  return !origin || origin === url.origin;
}

// ---- /api/forecast : optional endpoint for outside callers; the dashboard itself predicts in the browser ----
async function handleApi(request, env, url) {
  if (url.pathname !== '/api/forecast') return json({ error: 'Not found' }, 404);
  if (request.method !== 'POST') return json({ error: 'Use POST' }, 405, { Allow: 'POST' });
  if (!sameOrigin(request, url)) return json({ error: 'Forbidden' }, 403);
  let body;
  try { body = await request.json(); } catch { return json({ error: 'Send JSON such as {"input": 12}' }, 400); }
  const x = Number(body && body.input);
  if (!Number.isFinite(x)) return json({ error: 'input must be a number' }, 400);
  const lookup = await readAsset(env, url, '/data/monitor/forecast_lookup.json');
  const table = lookup && Array.isArray(lookup.table) ? lookup.table.filter(r => r && Number.isFinite(Number(r.x))) : [];
  if (table.length === 0) return json({ error: 'No lookup table is available for this project' }, 404);
  const nearest = table.reduce((best, r) => (Math.abs(r.x - x) < Math.abs(best.x - x) ? r : best), table[0]);
  return json({
    input: x,
    matched_input: nearest.x,
    value: nearest.value ?? null,
    low: nearest.low ?? null,
    high: nearest.high ?? null,
  });
}

// ---- /mcp : read-only MCP server (Streamable HTTP, stateless, JSON responses) ----
const TOOLS = [
  { name: 'get_kpis', outcome: 'understand', key: 'kpis', fallback: 'understand/kpis.json', description: 'Current key numbers for the business.' },
  { name: 'get_segments', outcome: 'understand', key: 'segments', fallback: 'understand/segments.json', description: 'Customer or record segments with sizes.' },
  { name: 'get_anomalies', outcome: 'understand', key: 'anomalies', fallback: 'understand/anomalies.json', description: 'Unusual days or records the analysis flagged.' },
  { name: 'get_insights', outcome: 'decide', key: 'insights', fallback: 'decide/insights.json', description: 'Findings with evidence and the action to take. Optional severity filter.', severity: true },
  { name: 'get_recommendations', outcome: 'decide', key: 'recommendations', fallback: 'decide/recommendations.json', description: 'Prioritised actions.' },
  { name: 'get_forecast', outcome: 'monitor', key: 'forecast', fallback: 'monitor/forecast.json', description: 'Forecast with its held-out error.' },
  { name: 'get_alerts', outcome: 'monitor', key: 'alerts', fallback: 'monitor/alerts.json', description: 'Active alerts.' },
  { name: 'get_summary', outcome: 'meta', key: 'summary', fallback: 'meta/summary.json', description: 'Project summary and data freshness.' },
];

function toolList() {
  return TOOLS.map(t => ({
    name: t.name,
    description: t.description,
    inputSchema: t.severity
      ? { type: 'object', properties: { severity: { type: 'string', enum: ['HIGH', 'MEDIUM', 'LOW', 'ALL'] } }, additionalProperties: false }
      : { type: 'object', properties: {}, additionalProperties: false },
    annotations: { readOnlyHint: true },
  }));
}

function safeEqual(a, b) {
  const enc = new TextEncoder();
  const x = enc.encode(String(a));
  const y = enc.encode(String(b));
  let diff = x.length ^ y.length;
  for (let i = 0; i < Math.max(x.length, y.length); i++) diff |= (x[i] || 0) ^ (y[i] || 0);
  return diff === 0;
}

function originAllowed(origin, env) {
  const list = String(env.MCP_ALLOWED_ORIGINS || '').split(',').map(s => s.trim()).filter(Boolean);
  return list.includes(origin);
}

async function handleMcp(request, env, url) {
  const mode = String(env.MCP_MODE || 'off').toLowerCase();
  if (mode === 'off') return json({ error: 'MCP access is turned off for this site' }, 404);
  if (mode !== 'open' && mode !== 'token') return json({ error: 'MCP_MODE must be off, token or open' }, 500);
  if (request.method !== 'POST') return json({ error: 'Use POST' }, 405, { Allow: 'POST' });
  const origin = request.headers.get('Origin');
  if (origin && origin !== url.origin && !originAllowed(origin, env)) return json({ error: 'Forbidden origin' }, 403);
  if (mode === 'token') {
    const header = request.headers.get('Authorization') || '';
    const given = header.startsWith('Bearer ') ? header.slice(7) : '';
    if (!env.MCP_TOKEN || !safeEqual(given, env.MCP_TOKEN)) {
      return json({ error: 'Unauthorized' }, 401, { 'WWW-Authenticate': 'Bearer' });
    }
  }
  let message;
  try { message = await request.json(); } catch { return json(rpcError(null, -32700, 'Parse error'), 400); }
  const batch = Array.isArray(message);
  const replies = [];
  for (const m of batch ? message : [message]) {
    const reply = await handleRpc(m, env, url);
    if (reply) replies.push(reply);
  }
  if (replies.length === 0) return new Response(null, { status: 202 });
  return json(batch ? replies : replies[0]);
}

function rpcError(id, code, message) {
  return { jsonrpc: '2.0', id: id === undefined ? null : id, error: { code, message } };
}

async function handleRpc(m, env, url) {
  if (!m || m.jsonrpc !== '2.0' || typeof m.method !== 'string') return rpcError(m && m.id, -32600, 'Invalid request');
  const isNotification = m.id === undefined || m.id === null;
  if (isNotification) return null;
  switch (m.method) {
    case 'initialize': {
      const asked = m.params && m.params.protocolVersion;
      const protocolVersion = MCP_PROTOCOLS.includes(asked) ? asked : MCP_PROTOCOLS[0];
      return {
        jsonrpc: '2.0', id: m.id,
        result: {
          protocolVersion,
          capabilities: { tools: { listChanged: false } },
          serverInfo: SERVER_INFO,
          instructions: 'Read-only business analytics. All numbers come from the latest published analysis run.',
        },
      };
    }
    case 'ping':
      return { jsonrpc: '2.0', id: m.id, result: {} };
    case 'tools/list':
      return { jsonrpc: '2.0', id: m.id, result: { tools: toolList() } };
    case 'tools/call': {
      const name = m.params && m.params.name;
      const tool = TOOLS.find(t => t.name === name);
      if (!tool) return rpcError(m.id, -32602, 'Unknown tool: ' + String(name));
      const contract = await loadContract(env, url);
      const path = contractPath(contract, tool.outcome, tool.key, tool.fallback);
      let data = await readAsset(env, url, path);
      if (data === null) {
        return { jsonrpc: '2.0', id: m.id, result: { isError: true, content: [{ type: 'text', text: 'No data is available for ' + tool.name + ' yet.' }] } };
      }
      const wanted = String((m.params.arguments && m.params.arguments.severity) || 'ALL').toUpperCase();
      if (tool.severity && wanted !== 'ALL' && data && Array.isArray(data.items)) {
        data = { ...data, items: data.items.filter(i => i && i.severity === wanted) };
      }
      return { jsonrpc: '2.0', id: m.id, result: { content: [{ type: 'text', text: fitJson(data) }] } };
    }
    default:
      return rpcError(m.id, -32601, 'Method not found: ' + m.method);
  }
}

function fitJson(data) {
  let text = JSON.stringify(data);
  if (text.length <= MAX_CHARS) return text;
  if (data && Array.isArray(data.items)) {
    let items = data.items;
    while (items.length > 1 && text.length > MAX_CHARS) {
      items = items.slice(0, Math.ceil(items.length / 2));
      text = JSON.stringify({ ...data, items, truncated: true });
    }
    if (text.length <= MAX_CHARS) return text;
  }
  return JSON.stringify({ truncated: true, note: 'Result too large to return in full' });
}
"""

FILES["src/utils/errors.js"] = r"""export class DataError extends Error {
  constructor(kind, message) {
    super(message);
    this.name = 'DataError';
    this.kind = kind; // missing | empty | invalid | shape | skipped | network
  }
}
"""

FILES["src/utils/datasets.js"] = r"""import * as A from './adapters.js';

export const DATASETS = {
  summary:         { outcome: 'meta',       key: 'summary',         fallback: 'meta/summary.json',                 adapt: A.adaptSummary },
  runLog:          { outcome: 'meta',       key: 'run_log',         fallback: 'meta/run_log.json',                 adapt: A.adaptRunLog },
  kpis:            { outcome: 'understand', key: 'kpis',            fallback: 'understand/kpis.json',              adapt: A.adaptKpis },
  charts:          { outcome: 'understand', key: 'charts',          fallback: 'understand/charts.json',            adapt: A.adaptCharts },
  segments:        { outcome: 'understand', key: 'segments',        fallback: 'understand/segments.json',          adapt: A.adaptSegments },
  anomalies:       { outcome: 'understand', key: 'anomalies',       fallback: 'understand/anomalies.json',         adapt: A.adaptAnomalies },
  explorer:        { outcome: 'understand', key: 'explorer',        fallback: 'understand/explorer.json',          adapt: A.adaptCube },
  insights:        { outcome: 'decide',     key: 'insights',        fallback: 'decide/insights.json',              adapt: A.adaptInsights },
  recommendations: { outcome: 'decide',     key: 'recommendations', fallback: 'decide/recommendations.json',       adapt: A.adaptRecommendations },
  simulations:     { outcome: 'decide',     key: 'simulations',     fallback: 'decide/simulations/index.json',     adapt: A.adaptSimulationIndex },
  goals:           { outcome: 'decide',     key: 'goals',           fallback: 'decide/goals.json',                 adapt: A.adaptGoals },
  forecast:        { outcome: 'monitor',    key: 'forecast',        fallback: 'monitor/forecast.json',             adapt: A.adaptForecast },
  forecastLookup:  { outcome: 'monitor',    key: 'forecast_lookup', fallback: 'monitor/forecast_lookup.json',      adapt: A.adaptForecastLookup },
  scorer:          { outcome: 'monitor',    key: 'scorer',          fallback: 'monitor/scorer.json',               adapt: A.adaptScorer },
  goalProgress:    { outcome: 'monitor',    key: 'goal_progress',   fallback: 'monitor/goal_progress.json',        adapt: A.adaptGoalProgress },
  alerts:          { outcome: 'monitor',    key: 'alerts',          fallback: 'monitor/alerts.json',               adapt: A.adaptAlerts },
};

export function resolveDatasetPath(contract, def) {
  const rel = contract && contract.outcomes && contract.outcomes[def.outcome] && contract.outcomes[def.outcome][def.key];
  const ok = typeof rel === 'string' && rel.endsWith('.json') && !rel.includes('..');
  return '/data/' + String(ok ? rel : def.fallback).replace(/^\/+/, '');
}

// Detail files that an index points to (for example one simulation); the relative path was checked by its adapter
export function dataPath(rel) {
  const clean = String(rel || '');
  if (clean.includes('..') || !clean.endsWith('.json')) return null;
  return '/data/' + clean.replace(/^\/+/, '');
}
"""

FILES["src/utils/formatters.js"] = r"""export function formatKind(unit) {
  const u = String(unit || '').toLowerCase();
  if (u === 'currency' || u === 'percent' || u === 'integer') return u;
  return 'decimal';
}

export function createFormatter(locale, currency) {
  const loc = locale || 'en-US';
  const makeNumber = opts => {
    try { return new Intl.NumberFormat(loc, opts); } catch { return new Intl.NumberFormat('en-US', opts); }
  };
  let money = null;
  try {
    if (currency && currency.code) money = new Intl.NumberFormat(loc, { style: 'currency', currency: currency.code, maximumFractionDigits: 0 });
  } catch { money = null; }
  const whole = makeNumber({ maximumFractionDigits: 0 });
  const decimal = makeNumber({ maximumFractionDigits: 2 });
  const oneDecimal = makeNumber({ minimumFractionDigits: 1, maximumFractionDigits: 1 });
  const compactFmt = makeNumber({ notation: 'compact', maximumFractionDigits: 1 });
  let dateFmt;
  try { dateFmt = new Intl.DateTimeFormat(loc, { dateStyle: 'medium' }); } catch { dateFmt = new Intl.DateTimeFormat('en-US', { dateStyle: 'medium' }); }
  let rel = null;
  try { rel = new Intl.RelativeTimeFormat(loc, { numeric: 'auto' }); } catch { rel = null; }

  const toNumber = v => (typeof v === 'number' ? v : Number(v));

  function value(v, format) {
    if (v === null || v === undefined || v === '') return '-';
    if (format === 'text') return String(v);
    const n = toNumber(v);
    if (!Number.isFinite(n)) return String(v);
    switch (format) {
      case 'currency':
        if (money) return money.format(n);
        return (currency && currency.symbol ? currency.symbol : '') + whole.format(n);
      case 'percent': return oneDecimal.format(n) + '%';
      case 'integer': return whole.format(n);
      default: return decimal.format(n);
    }
  }

  function compact(v) {
    const n = toNumber(v);
    return Number.isFinite(n) ? compactFmt.format(n) : String(v);
  }

  function percent(v) { return value(v, 'percent'); }

  function date(iso) {
    const d = new Date(iso);
    return Number.isNaN(d.getTime()) ? String(iso === null || iso === undefined ? '' : iso) : dateFmt.format(d);
  }

  function ago(iso) {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return String(iso === null || iso === undefined ? '' : iso);
    const seconds = Math.round((d.getTime() - Date.now()) / 1000);
    const steps = [['year', 31536000], ['month', 2592000], ['day', 86400], ['hour', 3600], ['minute', 60]];
    for (const [unit, size] of steps) {
      if (Math.abs(seconds) >= size) {
        const count = Math.round(seconds / size);
        return rel ? rel.format(count, unit) : Math.abs(count) + ' ' + unit + 's ago';
      }
    }
    return 'just now';
  }

  return { value, compact, percent, date, ago };
}
"""

FILES["src/utils/text.js"] = r"""export function refreshHint() {
  const dev = typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.DEV;
  return dev
    ? 'In the backend folder run main.py and then export_for_frontend.py, then run npm run check in this folder.'
    : 'The analysis data for this section was not published with this site. Run the backend steps again and publish a new version.';
}

export function truncate(value, max) {
  const s = String(value === null || value === undefined ? '' : value);
  return s.length > max ? s.slice(0, Math.max(1, max - 1)) + '\u2026' : s;
}

export function pluralize(word) {
  const w = String(word);
  if (/[^aeiou]y$/i.test(w)) return w.slice(0, -1) + 'ies';
  if (/(s|x|z|ch|sh)$/i.test(w)) return w + 'es';
  return w + 's';
}

// Splits text so a search match can be wrapped in a mark element
export function highlightParts(text, query) {
  const s = String(text === null || text === undefined ? '' : text);
  const q = String(query || '').trim();
  if (!q) return [{ text: s, hit: false }];
  const escaped = q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const pieces = s.split(new RegExp('(' + escaped + ')', 'gi'));
  return pieces.filter(p => p !== '').map(p => ({ text: p, hit: p.toLowerCase() === q.toLowerCase() }));
}
"""

FILES["src/utils/sim.js"] = r"""export function interpolate(table, x) {
  if (!Array.isArray(table) || table.length === 0) return null;
  if (x <= table[0].x) return table[0].values;
  const last = table[table.length - 1];
  if (x >= last.x) return last.values;
  let i = 1;
  while (i < table.length && table[i].x < x) i += 1;
  const a = table[i - 1];
  const b = table[i];
  const t = (x - a.x) / (b.x - a.x || 1);
  const out = {};
  for (const key of Object.keys(a.values)) out[key] = a.values[key] + (b.values[key] - a.values[key]) * t;
  return out;
}
"""

FILES["src/utils/cube.js"] = r"""function finalize(metric, bucket, metricsByKey) {
  const cell = bucket[metric.key] || { sum: 0, n: 0 };
  switch (metric.agg) {
    case 'mean': return cell.n ? cell.sum / cell.n : 0;
    case 'rate': return cell.n ? (cell.sum / cell.n) * 100 : 0;
    case 'count': return cell.n;
    case 'ratio': {
      const num = bucket[metric.num] ? bucket[metric.num].sum : 0;
      const den = bucket[metric.den] ? bucket[metric.den].sum : 0;
      const ratio = den ? num / den : 0;
      return metricsByKey[metric.key] && metricsByKey[metric.key].format === 'percent' ? ratio * 100 : ratio;
    }
    default: return cell.sum;
  }
}

// filters: { <dimensionKey>: value, _from: 'YYYY-MM', _to: 'YYYY-MM' }
// groupBy: a dimension key, '_time' or '_all'; skipDim ignores that dimension's own filter (cross-filter behaviour)
export function aggregate(cube, filters, groupBy, metricKey, skipDim) {
  const metricsByKey = Object.fromEntries(cube.metrics.map(m => [m.key, m]));
  const metric = metricsByKey[metricKey];
  if (!metric) return [];
  const buckets = new Map();
  for (const row of cube.rows) {
    let keep = true;
    for (const [dim, value] of Object.entries(filters)) {
      if (dim === '_from' || dim === '_to' || dim === skipDim) continue;
      if (value && row.d[dim] !== value) { keep = false; break; }
    }
    if (keep && filters._from && row.t < filters._from) keep = false;
    if (keep && filters._to && row.t > filters._to) keep = false;
    if (!keep) continue;
    let label;
    if (groupBy === '_time') label = row.t;
    else if (groupBy === '_all') label = 'All';
    else label = row.d[groupBy] === undefined ? 'Unknown' : row.d[groupBy];
    const bucket = buckets.get(label) || {};
    for (const [key, cell] of Object.entries(row.m)) {
      const acc = bucket[key] || { sum: 0, n: 0 };
      acc.sum += cell.sum;
      acc.n += cell.n;
      bucket[key] = acc;
    }
    buckets.set(label, bucket);
  }
  const out = [...buckets.entries()].map(([label, bucket]) => ({ label, value: finalize(metric, bucket, metricsByKey) }));
  return groupBy === '_time' ? out.sort((a, b) => (a.label < b.label ? -1 : 1)) : out.sort((a, b) => b.value - a.value);
}

export function totals(cube, filters, metricKey) {
  const rows = aggregate(cube, filters, '_all', metricKey);
  return rows.length ? rows[0].value : 0;
}
"""
FILES["src/utils/adapters.js"] = r"""import { DataError } from './errors.js';

const asNumber = v => {
  if (typeof v === 'number') return Number.isFinite(v) ? v : null;
  if (v === null || v === undefined) return null;
  const cleaned = String(v).replace(/[,\s$\u20ac\u00a3\u00a5%]/g, '');
  if (!/^[-+]?(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?$/.test(cleaned)) return null;
  const n = Number(cleaned);
  return Number.isFinite(n) ? n : null;
};
const asText = (v, fallback = '') => (v === null || v === undefined ? fallback : String(v));
export const humanize = key =>
  asText(key).replace(/[_\-]+/g, ' ').replace(/\s+/g, ' ').trim().replace(/^./, c => c.toUpperCase());
const listOf = raw => {
  if (Array.isArray(raw)) return raw;
  if (raw && Array.isArray(raw.items)) return raw.items;
  return null;
};
const shape = message => new DataError('shape', message);
const asYesNo = v => {
  const t = asText(v).trim().toLowerCase();
  if (['1', '1.0', 'true', 'yes', 'y'].includes(t)) return 'Yes';
  if (['0', '0.0', 'false', 'no', 'n'].includes(t)) return 'No';
  return null;
};
const isObject = v => v !== null && typeof v === 'object' && !Array.isArray(v);
const personal = /(^|_)(email|e_mail|phone|mobile|full_?name)(_|$)/i;

function guessFormat(key, value) {
  const k = asText(key).toLowerCase();
  if (/(rate|share|pct|percent|ratio)/.test(k)) return 'percent';
  if (/(revenue|sales|cost|price|mrr|arr|profit|amount|spend|value_total|margin_amt)/.test(k)) return 'currency';
  if (typeof value === 'number' && Number.isInteger(value)) return 'integer';
  if (typeof value === 'number') return 'decimal';
  return 'text';
}

export function adaptContract(raw) {
  if (!isObject(raw)) throw shape('The contract file has an unexpected shape');
  const proj = isObject(raw.project) ? raw.project : {};
  const t = isObject(raw.terminology) ? raw.terminology : {};
  const pick = (k, d) => asText(t[k]) || d;
  return {
    schemaVersion: asText(raw.schema_version, '1'),
    generatedAt: asText(raw.generated_at),
    project: {
      name: asText(proj.name, 'Dashboard'),
      domain: asText(proj.domain),
      clientId: asText(proj.client_id, 'project'),
      description: asText(proj.description),
    },
    terminology: {
      revenue: pick('revenue', 'Revenue'),
      customer: pick('customer', 'Customer'),
      product: pick('product', 'Product'),
      transaction: pick('transaction', 'Transaction'),
    },
    source: isObject(raw.source) ? raw.source : {},
    outcomes: isObject(raw.outcomes) ? raw.outcomes : {},
    model: isObject(raw.model) ? raw.model : null,
    forecaster: isObject(raw.forecaster) ? raw.forecaster : null,
    frontend: isObject(raw.frontend) ? raw.frontend : {},
  };
}

export function adaptSummary(raw) {
  if (!isObject(raw)) throw shape('The summary file has an unexpected shape');
  const range = isObject(raw.date_range) ? raw.date_range : {};
  const cur = isObject(raw.currency) && raw.currency.code ? { code: asText(raw.currency.code), symbol: asText(raw.currency.symbol) } : null;
  return {
    project: asText(raw.project),
    domain: asText(raw.domain),
    description: asText(raw.description),
    lastRun: asText(raw.last_run),
    rows: asNumber(raw.rows),
    dateRange: { start: asText(range.start), end: asText(range.end) },
    currency: cur,
    locale: asText(raw.locale, 'en-US') || 'en-US',
    source: asText(raw.source),
  };
}

export function adaptRunLog(raw) {
  const runs = Array.isArray(raw) ? raw : (raw && Array.isArray(raw.runs) ? raw.runs : null);
  if (!runs) throw shape('The run log has an unexpected shape');
  return runs.filter(isObject).map(r => ({
    started: asText(r.started),
    finished: asText(r.finished),
    stages: (Array.isArray(r.stages) ? r.stages : []).filter(isObject).map(s => ({
      name: asText(s.name), status: asText(s.status), seconds: asNumber(s.seconds), reason: asText(s.reason),
    })),
  }));
}

export function adaptKpis(raw) {
  let rows = listOf(raw);
  if (!rows && isObject(raw)) {
    rows = Object.entries(raw)
      .filter(([k, v]) => !k.startsWith('_') && k !== 'generated_at' && ['number', 'string', 'boolean'].includes(typeof v))
      .map(([key, value]) => ({ key, value }));
  }
  if (!rows) throw shape('The key numbers file has an unexpected shape');
  const out = rows
    .map((k, i) => {
      if (!k || typeof k !== 'object') return null;
      const key = asText(k.key ?? k.id ?? k.label ?? 'kpi_' + i);
      let value = typeof k.value === 'boolean' ? (k.value ? 'Yes' : 'No') : k.value;
      if (value === undefined || value === null) return null;
      let format = k.format || guessFormat(key, value);
      const n = asNumber(value);
      if (format !== 'text' && n === null) format = 'text';
      if (!k.format && format === 'percent' && n !== null && Math.abs(n) <= 1) value = n * 100;
      return { key, label: asText(k.label, humanize(key)), value, format, trend: asNumber(k.trend), note: asText(k.note) };
    })
    .filter(Boolean);
  if (out.length === 0) throw shape('No usable key numbers found');
  return out;
}

export function adaptChart(raw) {
  if (!raw || typeof raw !== 'object') throw shape('A chart file has an unexpected shape');
  const type = asText(raw.type, 'bar').toLowerCase();
  let rows = Array.isArray(raw.data) ? raw.data : null;
  if (!rows && Array.isArray(raw.x) && Array.isArray(raw.y)) {
    if (raw.x.length !== raw.y.length) throw shape('Chart x and y lengths differ');
    rows = raw.x.map((x, i) => ({ label: x, value: raw.y[i] }));
  }
  if (!rows) throw shape('Chart has no data');
  let cleaned;
  if (type === 'scatter') {
    cleaned = rows.map(r => ({ x: asNumber(r && r.x), y: asNumber(r && r.y), label: asText(r && r.label) }))
      .filter(r => r.x !== null && r.y !== null).slice(0, 1500);
  } else if (type === 'heatmap') {
    cleaned = rows.map(r => ({ row: asText(r && r.row), col: asText(r && r.col), value: asNumber(r && r.value) }))
      .filter(r => r.value !== null);
  } else {
    cleaned = rows.map(r => ({ label: asText(r && (r.label ?? r.x)), value: asNumber(r && (r.value ?? r.y)) }))
      .filter(r => r.value !== null);
  }
  if (cleaned.length === 0) throw shape('Chart has no plottable rows');
  const known = ['bar', 'line', 'histogram', 'scatter', 'heatmap', 'pie', 'doughnut'];
  return {
    id: asText(raw.id, 'chart'), title: asText(raw.title, 'Chart'), type: known.includes(type) ? type : 'bar',
    question: asText(raw.question), outcome: asText(raw.outcome),
    xLabel: asText(raw.x_label), yLabel: asText(raw.y_label), rows: cleaned,
  };
}

export function adaptCharts(raw) {
  const rows = listOf(raw);
  if (!rows) throw shape('The charts file has an unexpected shape');
  const out = [];
  for (const r of rows) { try { out.push(adaptChart(r)); } catch { /* one bad chart never hides the others */ } }
  if (out.length === 0) throw shape('No usable charts found');
  return out;
}

export function adaptSegments(raw) {
  const rows = listOf(raw);
  if (!rows) throw shape('The segments file has an unexpected shape');
  const items = rows.filter(isObject).map((s, i) => {
    const summary = {};
    if (isObject(s.summary)) {
      for (const [k, v] of Object.entries(s.summary)) {
        const n = asNumber(v);
        if (n !== null && !personal.test(k)) summary[k] = n;
      }
    }
    return { name: asText(s.name, 'Segment ' + (i + 1)), size: asNumber(s.size) ?? 0, share: asNumber(s.share), description: asText(s.description), summary };
  });
  if (items.length === 0) throw shape('No segments found');
  const total = items.reduce((acc, s) => acc + s.size, 0);
  for (const s of items) if (s.share === null) s.share = total ? (s.size / total) * 100 : 0;
  return { method: asText(raw && raw.method), items };
}

export function adaptAnomalies(raw) {
  const rows = listOf(raw);
  if (!rows) throw shape('The anomalies file has an unexpected shape');
  const items = rows.filter(isObject).map((a, i) => ({
    id: asText(a.id, String(i + 1)),
    date: a.date === null || a.date === undefined ? null : asText(a.date),
    metric: asText(a.metric),
    value: asNumber(a.value),
    expected: asNumber(a.expected),
    score: asNumber(a.score),
    reason: asText(a.reason),
  }));
  return {
    method: asText(raw && raw.method),
    total: asNumber(raw && raw.total) ?? items.length,
    rate: asNumber(raw && raw.rate),
    items,
  };
}

const SEVERITY_RANK = { HIGH: 0, MEDIUM: 1, LOW: 2 };
function normSeverity(v) {
  const s = asText(v).toUpperCase();
  if (s === 'HIGH' || s === 'CRITICAL') return 'HIGH';
  if (s === 'MEDIUM' || s === 'MED') return 'MEDIUM';
  return 'LOW';
}

export function adaptInsights(raw) {
  const rows = listOf(raw);
  if (!rows) throw shape('The insights file has an unexpected shape');
  const items = rows.filter(r => isObject(r) && r.finding).map((r, i) => ({
    id: 'insight-' + i,
    severity: normSeverity(r.severity),
    category: asText(r.category, 'General'),
    finding: asText(r.finding),
    evidence: asText(r.evidence),
    action: asText(r.action),
    outcome: asText(r.outcome),
  }));
  items.sort((a, b) => SEVERITY_RANK[a.severity] - SEVERITY_RANK[b.severity]);
  return items;
}

function normPriority(v) {
  const m = asText(v).toUpperCase().match(/P?([1-4])/);
  return 'P' + (m ? m[1] : '4');
}

export function adaptRecommendations(raw) {
  const rows = listOf(raw);
  if (!rows) throw shape('The recommendations file has an unexpected shape');
  const items = rows.filter(r => isObject(r) && (r.title || r.action)).map((r, i) => ({
    id: 'rec-' + i,
    priority: normPriority(r.priority),
    title: asText(r.title, asText(r.action)),
    action: asText(r.action),
    evidence: asText(r.evidence),
    impact: asText(r.impact),
    when: asText(r.when),
    count: asNumber(r.count),
  }));
  items.sort((a, b) => (a.priority < b.priority ? -1 : a.priority > b.priority ? 1 : 0));
  return items;
}

export function adaptSimulationIndex(raw) {
  const rows = listOf(raw);
  if (!rows) throw shape('The simulations index has an unexpected shape');
  return rows.filter(r => isObject(r) && r.id).map(r => {
    const id = asText(r.id);
    const file = asText(r.file, 'decide/simulations/' + id + '.json');
    if (file.includes('..')) throw shape('A simulation file path is not allowed');
    return { id, title: asText(r.title, humanize(id)), file };
  });
}

export function adaptSimulation(raw) {
  if (!isObject(raw)) throw shape('A simulation file has an unexpected shape');
  const v = isObject(raw.variable) ? raw.variable : null;
  if (!v) throw shape('The simulation has no input variable');
  const table = (Array.isArray(raw.table) ? raw.table : []).map(r => {
    const values = {};
    if (r && isObject(r.values)) for (const [k, val] of Object.entries(r.values)) { const n = asNumber(val); if (n !== null) values[k] = n; }
    return { x: asNumber(r && r.x), values };
  }).filter(r => r.x !== null && Object.keys(r.values).length > 0).sort((a, b) => a.x - b.x);
  if (table.length === 0) throw shape('The simulation table has no usable rows');
  const min = asNumber(v.min) ?? table[0].x;
  const max = asNumber(v.max) ?? table[table.length - 1].x;
  const outputs = (Array.isArray(raw.outputs) ? raw.outputs : []).filter(o => isObject(o) && o.key).map(o => ({
    key: asText(o.key), label: asText(o.label, humanize(o.key)), format: asText(o.format, 'decimal'),
  }));
  if (outputs.length === 0) for (const k of Object.keys(table[0].values)) outputs.push({ key: k, label: humanize(k), format: 'decimal' });
  return {
    id: asText(raw.id), title: asText(raw.title), description: asText(raw.description),
    variable: {
      key: asText(v.key), label: asText(v.label, humanize(v.key)), unit: asText(v.unit), min, max,
      step: asNumber(v.step) || (max - min) / 20 || 1,
      default: asNumber(v.default) ?? min,
      format: asText(v.format, 'decimal'),
    },
    outputs,
    table,
    assumptions: (Array.isArray(raw.assumptions) ? raw.assumptions : []).map(a => asText(a)),
  };
}

export function adaptGoals(raw) {
  if (!raw || typeof raw !== 'object') throw shape('The goals file has an unexpected shape');
  const list = Array.isArray(raw) ? raw : (Array.isArray(raw.items) ? raw.items : null);
  const out = [];
  if (list) {
    list.filter(isObject).forEach((g, i) => {
      const key = asText(g.key ?? g.id ?? g.name ?? 'goal_' + i);
      out.push({ key, label: asText(g.label, humanize(key)), target: asNumber(g.target ?? g.value), unit: asText(g.unit ?? g.units), description: asText(g.description), clientSets: Boolean(g.client_sets) });
    });
  } else {
    for (const [key, g] of Object.entries(raw)) {
      if (key.startsWith('_') || key === 'generated_at' || key === 'schema_version') continue;
      if (isObject(g)) {
        out.push({ key, label: asText(g.label, humanize(key)), target: asNumber(g.target ?? g.value), unit: asText(g.unit ?? g.units), description: asText(g.description), clientSets: Boolean(g.client_sets) });
      } else if (typeof g === 'number' || typeof g === 'string') {
        out.push({ key, label: humanize(key), target: asNumber(g), unit: '', description: '', clientSets: false });
      }
    }
  }
  return out;
}

const STATUS_OK = ['on_track', 'at_risk', 'off_track', 'no_target'];
export function adaptGoalProgress(raw) {
  const rows = listOf(raw);
  if (!rows) throw shape('The goal progress file has an unexpected shape');
  return rows.filter(r => isObject(r) && (r.key || r.label)).map(r => {
    const status = asText(r.status).toLowerCase();
    return {
      key: asText(r.key ?? r.label), label: asText(r.label, humanize(r.key)), target: asNumber(r.target), actual: asNumber(r.actual),
      unit: asText(r.unit), pct: asNumber(r.pct), status: STATUS_OK.includes(status) ? status : 'no_target',
    };
  });
}

export function adaptAlerts(raw) {
  const rows = listOf(raw);
  if (!rows) throw shape('The alerts file has an unexpected shape');
  const items = rows.filter(r => isObject(r) && (r.title || r.message)).map((r, i) => ({
    id: 'alert-' + i,
    severity: normSeverity(r.severity),
    title: asText(r.title, asText(r.message)),
    message: asText(r.message),
    metric: asText(r.metric),
    value: asNumber(r.value),
    threshold: asNumber(r.threshold),
    since: asText(r.since),
  }));
  items.sort((a, b) => SEVERITY_RANK[a.severity] - SEVERITY_RANK[b.severity]);
  return items;
}

export function adaptForecast(raw) {
  if (!raw || typeof raw !== 'object') throw shape('The forecast file has an unexpected shape');
  const pickKey = (row, keys) => keys.find(k => row[k] !== undefined && row[k] !== null);
  let meta = {};
  let history = [];
  let forecast = [];
  if (Array.isArray(raw)) {
    const rows = raw.filter(isObject);
    const tk = rows.length ? pickKey(rows[0], ['t', 'date', 'ds', 'week', 'period']) : null;
    const vk = rows.length ? pickKey(rows[0], ['forecast', 'prediction', 'yhat', 'value']) : null;
    if (!tk || !vk) throw shape('The forecast rows have no time or value column');
    forecast = rows.map(r => ({ t: asText(r[tk]), value: asNumber(r[vk]), low: asNumber(r.low ?? r.yhat_lower), high: asNumber(r.high ?? r.yhat_upper) }));
  } else {
    meta = raw;
    history = (Array.isArray(raw.history) ? raw.history : []).filter(isObject).map(r => ({ t: asText(r.t ?? r.date), value: asNumber(r.value) }));
    forecast = (Array.isArray(raw.forecast) ? raw.forecast : []).filter(isObject).map(r => ({ t: asText(r.t ?? r.date), value: asNumber(r.value ?? r.forecast), low: asNumber(r.low), high: asNumber(r.high) }));
  }
  history = history.filter(r => r.t && r.value !== null);
  forecast = forecast.filter(r => r.t && r.value !== null);
  if (history.length === 0 && forecast.length === 0) throw shape('The forecast has no usable rows');
  const e = isObject(meta.error) ? meta.error : null;
  return {
    metric: asText(meta.metric), unit: asText(meta.unit), horizon: asText(meta.horizon), method: asText(meta.method),
    history, forecast,
    error: e ? { mae: asNumber(e.mae), mape: asNumber(e.mape), baselineMae: asNumber(e.baseline_mae), period: asText(e.period) } : null,
    note: asText(meta.note),
  };
}

export function adaptCube(raw) {
  if (!isObject(raw)) throw shape('The explorer file has an unexpected shape');
  const dimensions = (Array.isArray(raw.dimensions) ? raw.dimensions : []).filter(d => isObject(d) && d.key).map(d => ({
    key: asText(d.key), label: asText(d.label, humanize(d.key)), values: (Array.isArray(d.values) ? d.values : []).map(v => asText(v)),
  }));
  const metrics = (Array.isArray(raw.metrics) ? raw.metrics : []).filter(m => isObject(m) && m.key).map(m => ({
    key: asText(m.key), label: asText(m.label, humanize(m.key)), agg: asText(m.agg, 'sum'), format: asText(m.format, 'decimal'),
    num: asText(m.num), den: asText(m.den),
  }));
  if (metrics.length === 0) throw shape('The explorer file lists no metrics');
  const rows = [];
  for (const r of (Array.isArray(raw.rows) ? raw.rows : [])) {
    if (!isObject(r) || r.t === undefined || r.t === null || !isObject(r.m)) continue;
    const m = {};
    for (const [k, cell] of Object.entries(r.m)) {
      if (isObject(cell)) m[k] = { sum: asNumber(cell.sum) ?? 0, n: asNumber(cell.n) ?? 0 };
    }
    const d = {};
    if (isObject(r.d)) for (const [k, v] of Object.entries(r.d)) d[k] = asText(v);
    rows.push({ d, t: asText(r.t), m });
  }
  if (rows.length === 0) throw shape('The explorer file has no usable rows');
  const t = isObject(raw.time) ? raw.time : {};
  return { dimensions, metrics, time: { grain: asText(t.grain, 'month'), min: asText(t.min), max: asText(t.max) }, rows };
}

export function adaptScorer(raw) {
  if (!raw || typeof raw !== 'object') throw shape('The scoring file has an unexpected shape');
  const type = asText(raw.type).toLowerCase();
  if (type !== 'linear' && type !== 'knn') throw shape('Scoring type must be linear or knn');
  const task = asText(raw.task, 'classification').toLowerCase() === 'regression' ? 'regression' : 'classification';
  const fields = (Array.isArray(raw.fields) ? raw.fields : []).map(f => {
    if (!f || typeof f !== 'object' || !f.key) return null;
    const ftype = ['number', 'category', 'boolean'].includes(f.type) ? f.type : 'number';
    const options = ftype === 'boolean' ? ['No', 'Yes'] : (Array.isArray(f.options) ? f.options.map(o => asText(o)) : []);
    if (ftype !== 'number' && options.length === 0) return null;
    return {
      key: asText(f.key), label: asText(f.label, humanize(f.key)), type: ftype, unit: asText(f.unit),
      min: asNumber(f.min), max: asNumber(f.max), step: asNumber(f.step) || 1,
      default: ftype === 'number' ? asNumber(f.default)
        : ftype === 'boolean' ? asYesNo(f.default)
        : (f.default === undefined || f.default === null || !options.includes(asText(f.default)) ? null : asText(f.default)),
      options, help: asText(f.help),
    };
  }).filter(Boolean);
  if (fields.length === 0) throw shape('The scoring file lists no input fields');
  const keys = new Set(fields.map(f => f.key));
  const out = {
    type, task, fields,
    target: { label: asText(raw.target && raw.target.label, 'Predicted value'), format: asText(raw.target && raw.target.format, task === 'classification' ? 'percent' : 'decimal'), positive: asText(raw.target && raw.target.positive_label) },
    riskLevels: (Array.isArray(raw.risk_levels) ? raw.risk_levels : []).map(l => ({ max: asNumber(l && l.max), label: asText(l && l.label) })).filter(l => l.max !== null && l.label).sort((a, b) => a.max - b.max),
    fidelity: raw.fidelity && typeof raw.fidelity === 'object' ? { metric: asText(raw.fidelity.metric), value: asNumber(raw.fidelity.value), n: asNumber(raw.fidelity.n), quality: asText(raw.fidelity.quality), note: asText(raw.fidelity.note) } : null,
    note: asText(raw.note),
  };
  if (type === 'linear') {
    const lin = raw.linear;
    const terms = lin && Array.isArray(lin.terms) ? lin.terms : null;
    if (!lin || asNumber(lin.intercept) === null || !terms) throw shape('Linear scoring needs an intercept and terms');
    out.linear = {
      intercept: asNumber(lin.intercept), link: asText(lin.link, 'identity') === 'logit' ? 'logit' : 'identity',
      terms: terms.map(t => {
        if (!t || !keys.has(asText(t.field)) || asNumber(t.coef) === null) throw shape('A scoring term refers to an unknown field');
        const categorical = t.value !== undefined && t.value !== null;
        const owner = fields.find(f => f.key === asText(t.field));
        const termValue = categorical ? (owner && owner.type === 'boolean' ? (asYesNo(t.value) || asText(t.value)) : asText(t.value)) : null;
        return { field: asText(t.field), coef: asNumber(t.coef), value: termValue, mean: asNumber(t.mean) || 0, scale: asNumber(t.scale) || 1 };
      }),
    };
  } else {
    const knn = raw.knn;
    const ref = knn && Array.isArray(knn.reference) ? knn.reference : null;
    if (!ref) throw shape('Neighbour scoring needs a reference table');
    const reference = ref.map(r => ({ x: r && r.x && typeof r.x === 'object' ? r.x : null, y: asNumber(r && r.y) })).filter(r => r.x && r.y !== null);
    if (reference.length < 5) throw shape('The reference table is too small to predict from');
    const std = {};
    for (const f of fields) if (f.type === 'number') std[f.key] = asNumber(knn.std && knn.std[f.key]) || 1;
    out.knn = { k: Math.max(1, Math.round(asNumber(knn.k) || 25)), std, reference };
  }
  return out;
}

export function adaptForecastLookup(raw) {
  const table = raw && Array.isArray(raw.table) ? raw.table : null;
  if (!table) throw shape('The lookup file has an unexpected shape');
  const rows = table
    .map(r => ({ x: asNumber(r && r.x), value: asNumber(r && r.value), low: asNumber(r && r.low), high: asNumber(r && r.high) }))
    .filter(r => r.x !== null && r.value !== null)
    .sort((a, b) => a.x - b.x);
  if (rows.length === 0) throw shape('The lookup table has no usable rows');
  return { inputLabel: asText(raw.input_label, 'Input'), outputLabel: asText(raw.output_label, 'Result'), table: rows };
}
"""

FILES["src/utils/predict.js"] = r"""const sigmoid = z => 1 / (1 + Math.exp(-z));

export function defaultsFor(fields) {
  const out = {};
  for (const f of fields) {
    if (f.default !== null && f.default !== undefined && f.default !== '') out[f.key] = f.default;
    else if (f.type === 'number') out[f.key] = f.min !== null ? f.min : 0;
    else out[f.key] = f.options.length ? f.options[0] : '';
    if (f.type !== 'number' && f.options.length && !f.options.includes(String(out[f.key]))) out[f.key] = f.options[0];
  }
  return out;
}

// problems block the Predict button; warnings only show a caution under the field
export function validateInputs(fields, values) {
  const problems = [];
  const warnings = [];
  for (const f of fields) {
    const v = values[f.key];
    if (f.type === 'number') {
      const n = Number(v);
      if (v === '' || v === null || v === undefined || !Number.isFinite(n)) {
        problems.push({ key: f.key, message: f.label + ' needs a number' });
      } else if ((f.min !== null && n < f.min) || (f.max !== null && n > f.max)) {
        warnings.push({ key: f.key, message: f.label + ' is outside the range seen in the data (' + f.min + ' to ' + f.max + ')' });
      }
    } else if (!f.options.includes(String(v))) {
      problems.push({ key: f.key, message: 'Choose a value for ' + f.label });
    }
  }
  return { problems, warnings };
}

function numericOf(field, v) {
  if (typeof v === 'number') return v;
  const t = String(v).trim().toLowerCase();
  if (['yes', 'true', 'y'].includes(t)) return 1;
  if (['no', 'false', 'n'].includes(t)) return 0;
  const n = Number(v);
  if (Number.isFinite(n)) return n;
  const idx = field && Array.isArray(field.options) ? field.options.indexOf(String(v)) : -1;
  return idx >= 0 ? idx : 0;
}

function scoreLinear(scorer, values) {
  const { intercept, link, terms } = scorer.linear;
  let z = intercept;
  const drivers = [];
  for (const t of terms) {
    let contribution = 0;
    if (t.value === null) {
      const field = scorer.fields.find(f => f.key === t.field);
      contribution = ((numericOf(field, values[t.field]) - t.mean) / (t.scale || 1)) * t.coef;
    } else if (String(values[t.field]).trim().toLowerCase() === String(t.value).trim().toLowerCase()) {
      contribution = t.coef;
    }
    if (!Number.isFinite(contribution)) contribution = 0;
    z += contribution;
    drivers.push({ field: t.field, contribution });
  }
  if (!Number.isFinite(z)) z = intercept;
  const value = link === 'logit' ? sigmoid(z) * 100 : z;
  drivers.sort((a, b) => Math.abs(b.contribution) - Math.abs(a.contribution));
  return { value, low: null, high: null, drivers: drivers.slice(0, 3), neighbors: null };
}

function scoreKnn(scorer, values) {
  const { k, std, reference } = scorer.knn;
  const scored = reference
    .map(row => {
      let d = 0;
      for (const f of scorer.fields) {
        if (f.type === 'number') {
          const diff = (numericOf(f, values[f.key]) - numericOf(f, row.x[f.key])) / (std[f.key] || 1);
          d += Number.isFinite(diff) ? diff * diff : 0;
        } else if (String(values[f.key]) !== String(row.x[f.key])) {
          d += 1;
        }
      }
      return { d: Math.sqrt(d), y: row.y };
    })
    .sort((a, b) => a.d - b.d);
  const near = scored.slice(0, Math.max(1, Math.min(k, scored.length)));
  let weights = 0;
  let total = 0;
  for (const n of near) {
    const w = 1 / (n.d + 0.05);
    weights += w;
    total += w * n.y;
  }
  const ys = near.map(n => n.y).sort((a, b) => a - b);
  const at = p => ys[Math.min(ys.length - 1, Math.max(0, Math.round(p * (ys.length - 1))))];
  return { value: total / weights, low: at(0.1), high: at(0.9), drivers: [], neighbors: near.length };
}

export function riskLabel(levels, value) {
  if (!Array.isArray(levels) || levels.length === 0) return '';
  for (const level of levels) if (value <= level.max) return level.label;
  return levels[levels.length - 1].label;
}

export function predict(scorer, values) {
  const raw = scorer.type === 'linear' ? scoreLinear(scorer, values) : scoreKnn(scorer, values);
  const clamp = v => (v === null || scorer.task !== 'classification' ? v : Math.min(100, Math.max(0, v)));
  const value = clamp(raw.value);
  return {
    ...raw,
    value,
    low: clamp(raw.low),
    high: clamp(raw.high),
    label: scorer.task === 'classification' ? riskLabel(scorer.riskLevels, value) : '',
  };
}

// Forecast-only projects: read the value for a chosen future period
export function forecastAt(forecast, t) {
  const row = forecast.forecast.find(r => String(r.t) === String(t));
  return row ? { value: row.value, low: row.low, high: row.high } : null;
}

// Single-number lookup tables: linear interpolation, flagged when outside the table
export function lookupAt(table, x) {
  if (!Array.isArray(table) || table.length === 0) return null;
  const first = table[0];
  const last = table[table.length - 1];
  const pick = (a, b, t) => {
    const mixed = key => (a[key] === null || b[key] === null ? null : a[key] + (b[key] - a[key]) * t);
    return { value: mixed('value'), low: mixed('low'), high: mixed('high') };
  };
  if (x <= first.x) return { ...pick(first, first, 0), outside: x < first.x };
  if (x >= last.x) return { ...pick(last, last, 0), outside: x > last.x };
  let i = 1;
  while (i < table.length && table[i].x < x) i += 1;
  const a = table[i - 1];
  const b = table[i];
  return { ...pick(a, b, (x - a.x) / (b.x - a.x || 1)), outside: false };
}

// Says which Predict mode a build uses; each argument is { data, error }
export function predictMode(scorer, lookup, forecast) {
  if (scorer.data) return scorer.data.type === 'linear' ? 'model scoring (linear)' : 'model scoring (nearest neighbours)';
  if (lookup.data) return 'lookup table';
  if (forecast.data && forecast.data.forecast.length > 0) return 'forecast period';
  const why = [scorer, lookup, forecast].filter(q => q.error).map(q => q.error.message);
  return 'unavailable' + (why.length ? ' (' + why[0] + ')' : '');
}
"""
FILES["src/hooks/useData.js"] = r"""import { useCallback, useEffect, useState } from 'react';
import { DataError } from '../utils/errors.js';

const cache = new Map();

function toDataError(err) {
  return err instanceof DataError ? err : new DataError('shape', (err && err.message) || 'Unexpected data');
}

async function fetchJson(path, signal) {
  let res;
  try {
    res = await fetch(path, { signal, headers: { Accept: 'application/json' } });
  } catch (err) {
    if (err && err.name === 'AbortError') throw err;
    throw new DataError('network', 'Could not reach the server');
  }
  if (!res.ok) throw new DataError('missing', 'File not found: ' + path);
  const text = await res.text();
  if (!text.trim()) throw new DataError('empty', 'Empty file: ' + path);
  const type = res.headers.get('content-type') || '';
  if (type.includes('text/html') || text.trimStart().startsWith('<')) {
    throw new DataError('missing', 'File not found: ' + path);
  }
  try {
    return JSON.parse(text);
  } catch {
    throw new DataError('invalid', 'Invalid JSON: ' + path);
  }
}

function fromCache(path, adapt) {
  if (!path || !cache.has(path)) return { data: null, loading: true, error: null };
  const raw = cache.get(path);
  try {
    if (raw && typeof raw === 'object' && !Array.isArray(raw) && raw.status === 'skipped') {
      throw new DataError('skipped', raw.reason || 'This part of the analysis was skipped');
    }
    return { data: adapt ? adapt(raw) : raw, loading: false, error: null };
  } catch (err) {
    return { data: null, loading: false, error: toDataError(err) };
  }
}

export function useData(path, adapt, enabled = true) {
  const [tick, setTick] = useState(0);
  const [state, setState] = useState(() => (enabled ? fromCache(path, adapt) : { data: null, loading: true, error: null }));

  useEffect(() => {
    if (!enabled) return undefined;
    if (!path) {
      setState({ data: null, loading: false, error: new DataError('missing', 'No file is configured for this section') });
      return undefined;
    }
    if (cache.has(path)) {
      setState(fromCache(path, adapt));
      return undefined;
    }
    const controller = new AbortController();
    setState(prev => (prev.loading ? prev : { data: null, loading: true, error: null }));
    fetchJson(path, controller.signal)
      .then(raw => {
        cache.set(path, raw);
        if (!controller.signal.aborted) setState(fromCache(path, adapt));
      })
      .catch(err => {
        if ((err && err.name === 'AbortError') || controller.signal.aborted) return;
        setState({ data: null, loading: false, error: toDataError(err) });
      });
    return () => controller.abort();
    // adapt is a module-level function and never changes between renders
  }, [path, enabled, tick]);

  const reload = useCallback(() => {
    cache.delete(path);
    setTick(t => t + 1);
  }, [path]);

  return { ...state, reload };
}
"""

FILES["src/hooks/useContract.js"] = r"""import { useData } from './useData.js';
import { adaptContract } from '../utils/adapters.js';

export function useContract() {
  return useData('/data/frontend_contract.json', adaptContract);
}
"""

FILES["src/hooks/useDataset.js"] = r"""import { useData } from './useData.js';
import { useContract } from './useContract.js';
import { DATASETS, resolveDatasetPath } from '../utils/datasets.js';

export function useDataset(name) {
  const def = DATASETS[name];
  const contract = useContract();
  const path = def ? resolveDatasetPath(contract.data, def) : null;
  return useData(path, def ? def.adapt : undefined, !contract.loading);
}

export function useDataFile(path, adapt) {
  return useData(path, adapt, true);
}
"""

FILES["src/hooks/useHashRoute.js"] = r"""import { useCallback, useEffect, useState } from 'react';

function readHash() {
  return window.location.hash.replace(/^#\/?/, '');
}

export function useHashRoute(valid, fallback) {
  const [raw, setRaw] = useState(readHash);
  useEffect(() => {
    const onChange = () => setRaw(readHash());
    window.addEventListener('hashchange', onChange);
    return () => window.removeEventListener('hashchange', onChange);
  }, []);
  const route = valid.includes(raw) ? raw : fallback;
  const go = useCallback(id => { window.location.hash = '/' + id; }, []);
  return [route, go];
}
"""

FILES["src/hooks/useChartColors.js"] = r"""import { useEffect, useState } from 'react';

function readColors() {
  const cs = getComputedStyle(document.documentElement);
  const get = name => cs.getPropertyValue(name).trim();
  return {
    accent: get('--color-accent'),
    grid: get('--color-border'),
    text: get('--color-text-secondary'),
    textPrimary: get('--color-text-primary'),
    surface: get('--color-surface'),
    series: [1, 2, 3, 4, 5, 6].map(i => get('--chart-' + i)),
  };
}

export function useChartColors() {
  const [colors, setColors] = useState(readColors);
  useEffect(() => {
    const observer = new MutationObserver(() => setColors(readColors()));
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
    return () => observer.disconnect();
  }, []);
  return colors;
}
"""

FILES["src/context/TerminologyContext.jsx"] = r"""import { createContext, useCallback, useContext, useMemo } from 'react';
import { useContract } from '../hooks/useContract.js';
import { humanize } from '../utils/adapters.js';
import { pluralize } from '../utils/text.js';

const DEFAULTS = { revenue: 'Revenue', customer: 'Customer', product: 'Product', transaction: 'Transaction' };
const TerminologyContext = createContext(DEFAULTS);

export function TerminologyProvider({ children }) {
  const contract = useContract();
  const terms = useMemo(() => ({ ...DEFAULTS, ...(contract.data ? contract.data.terminology : {}) }), [contract.data]);
  return <TerminologyContext.Provider value={terms}>{children}</TerminologyContext.Provider>;
}

export function useTerm() {
  const terms = useContext(TerminologyContext);
  return useCallback((key, options) => {
    const opts = options || {};
    let word = terms[key] || humanize(key);
    if (opts.plural) word = pluralize(word);
    return opts.lower ? word.toLowerCase() : word;
  }, [terms]);
}
"""

FILES["src/context/FormatContext.jsx"] = r"""import { createContext, useContext, useMemo } from 'react';
import { useDataset } from '../hooks/useDataset.js';
import { createFormatter } from '../utils/formatters.js';

const FormatContext = createContext(createFormatter('en-US', null));

export function FormatProvider({ children }) {
  const summary = useDataset('summary');
  const fmt = useMemo(() => {
    const s = summary.data;
    return createFormatter(s ? s.locale : 'en-US', s ? s.currency : null);
  }, [summary.data]);
  return <FormatContext.Provider value={fmt}>{children}</FormatContext.Provider>;
}

export function useFormat() {
  return useContext(FormatContext);
}
"""

FILES["src/context/ExplorerContext.jsx"] = r"""import { createContext, useCallback, useContext, useMemo, useState } from 'react';

const ExplorerContext = createContext(null);

export function ExplorerProvider({ children }) {
  const [filters, setFilters] = useState({});
  const [metricKey, setMetricKey] = useState(null);

  const setFilter = useCallback((dim, value, toggle = true) => {
    setFilters(prev => {
      const next = { ...prev };
      if (!value || (toggle && prev[dim] === value)) delete next[dim];
      else next[dim] = value;
      return next;
    });
  }, []);
  const clearFilters = useCallback(() => setFilters({}), []);
  const activeCount = Object.keys(filters).length;

  const value = useMemo(
    () => ({ filters, setFilter, clearFilters, metricKey, setMetricKey, activeCount }),
    [filters, setFilter, clearFilters, metricKey, activeCount],
  );
  return <ExplorerContext.Provider value={value}>{children}</ExplorerContext.Provider>;
}

export function useExplorer() {
  const ctx = useContext(ExplorerContext);
  if (!ctx) throw new Error('Explorer controls need the explorer provider around them');
  return ctx;
}
"""

FILES["src/components/shared/Icon.jsx"] = r"""const PATHS = {
  sun: 'M12 4V2M12 22v-2M4 12H2M22 12h-2M5.6 5.6 4.2 4.2M19.8 19.8l-1.4-1.4M5.6 18.4l-1.4 1.4M19.8 4.2l-1.4 1.4M12 8a4 4 0 100 8 4 4 0 000-8z',
  moon: 'M21 12.8A9 9 0 1111.2 3a7 7 0 009.8 9.8z',
  up: 'M12 19V5M5 12l7-7 7 7',
  down: 'M12 5v14M19 12l-7 7-7-7',
  flat: 'M5 12h14',
  overview: 'M3 3h7v9H3zM14 3h7v5h-7zM14 12h7v9h-7zM3 16h7v5H3z',
  segments: 'M12 3a9 9 0 109 9h-9z',
  anomalies: 'M12 3l10 18H2zM12 10v5M12 18v.5',
  insights: 'M9 18h6M10 21h4M12 3a6 6 0 00-4 10.5c.7.7 1 1.5 1 2.5h6c0-1 .3-1.8 1-2.5A6 6 0 0012 3z',
  recommendations: 'M5 12l4 4 10-10',
  whatif: 'M4 6h16M4 12h16M4 18h16M8 4v4M16 10v4M10 16v4',
  goals: 'M12 12m-9 0a9 9 0 1018 0 9 9 0 10-18 0M12 12m-4 0a4 4 0 108 0 4 4 0 10-8 0M12 12h.01',
  forecast: 'M3 17l6-6 4 4 8-8M15 7h6v6',
  predict: 'M4 20V10M10 20V4M16 20v-8M22 20H2',
  progress: 'M4 12h16M4 6h10M4 18h13',
  alerts: 'M18 8a6 6 0 10-12 0c0 7-3 9-3 9h18s-3-2-3-9M10 21h4',
  explore: 'M11 4a7 7 0 100 14 7 7 0 000-14zM21 21l-4.3-4.3',
  guide: 'M4 4h12a4 4 0 014 4v12H8a4 4 0 01-4-4zM8 8h8M8 12h8',
  health: 'M3 12h4l3-8 4 16 3-8h4',
  close: 'M6 6l12 12M18 6L6 18',
};

export function Icon({ name, label }) {
  const d = PATHS[name] || PATHS.flat;
  return (
    <svg className="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden={label ? undefined : 'true'} role={label ? 'img' : undefined} aria-label={label || undefined}>
      <path d={d} />
    </svg>
  );
}
"""

FILES["src/components/shared/SkeletonCard.jsx"] = r"""export function SkeletonCard({ count = 1, height = 96 }) {
  const items = Array.from({ length: count }, (_, i) => i);
  return (
    <div className="grid" aria-busy="true" aria-label="Loading">
      {items.map(i => (
        <div className="card skeleton" key={'sk-' + i} style={{ height: (height / 16) + 'rem' }} />
      ))}
    </div>
  );
}
"""

FILES["src/components/shared/DataState.jsx"] = r"""import { SkeletonCard } from './SkeletonCard.jsx';
import { refreshHint } from '../../utils/text.js';

export function DataState({ query, label, skeleton }) {
  if (query.loading) return skeleton || <SkeletonCard count={2} height={96} />;
  const err = query.error;
  if (!err) return null;
  const retry = <button type="button" className="btn-secondary" onClick={query.reload}>Retry</button>;
  let body;
  switch (err.kind) {
    case 'skipped':
      body = <p>{'This section was skipped: ' + err.message}</p>;
      break;
    case 'missing':
    case 'empty':
      body = (
        <div>
          <p>{'No ' + label + ' yet. ' + refreshHint()}</p>
          {retry}
        </div>
      );
      break;
    case 'network':
      body = (
        <div>
          <p>{'Could not load ' + label + '. Check the connection.'}</p>
          {retry}
        </div>
      );
      break;
    default:
      body = (
        <div>
          <p>{'The ' + label + ' file is not in the expected format.'}</p>
          <p className="muted small">{err.message}</p>
        </div>
      );
  }
  return <div className="card state-box" role="status">{body}</div>;
}
"""

FILES["src/components/shared/ErrorBoundary.jsx"] = r"""import { Component } from 'react';

export class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { failed: false };
  }

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch() {
    // the fallback below is the only handling needed
  }

  render() {
    if (this.state.failed) {
      return (
        <div className="card state-box" role="alert">
          <p>{this.props.label ? this.props.label + ' could not be shown.' : 'This part of the page could not be shown.'}</p>
        </div>
      );
    }
    return this.props.children;
  }
}
"""

FILES["src/components/shared/SeverityBadge.jsx"] = r"""const WORDS = { HIGH: 'High', MEDIUM: 'Medium', LOW: 'Low' };

export function SeverityBadge({ severity }) {
  const key = String(severity || 'LOW').toUpperCase();
  return <span className={'badge badge-' + key.toLowerCase()}>{WORDS[key] || 'Low'}</span>;
}
"""

FILES["src/components/shared/PageSection.jsx"] = r"""export function PageSection({ title, intro, children }) {
  return (
    <section className="page-section">
      <header className="page-head">
        <h1>{title}</h1>
        {intro ? <p className="muted">{intro}</p> : null}
      </header>
      {children}
    </section>
  );
}
"""

FILES["src/components/shared/ThemeToggle.jsx"] = r"""import { useState } from 'react';
import { Icon } from './Icon.jsx';

export function ThemeToggle() {
  const [theme, setTheme] = useState(() => document.documentElement.getAttribute('data-theme') || 'light');
  const flip = () => {
    const next = theme === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    try { localStorage.setItem('theme', next); } catch { /* storage may be blocked; the choice still applies for this visit */ }
    setTheme(next);
  };
  return (
    <button type="button" className="icon-btn" onClick={flip} aria-label={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}>
      <Icon name={theme === 'dark' ? 'sun' : 'moon'} />
    </button>
  );
}
"""

FILES["src/components/shared/Sidebar.jsx"] = r"""import { useContract } from '../../hooks/useContract.js';
import { Icon } from './Icon.jsx';

export const NAV_GROUPS = [
  { title: 'Understand', items: [
    { id: 'understand/overview', label: 'Overview', icon: 'overview' },
    { id: 'understand/segments', label: 'Segments', icon: 'segments' },
    { id: 'understand/anomalies', label: 'Anomalies', icon: 'anomalies' },
  ] },
  { title: 'Decide', items: [
    { id: 'decide/insights', label: 'Insights', icon: 'insights' },
    { id: 'decide/recommendations', label: 'Recommendations', icon: 'recommendations' },
    { id: 'decide/what-if', label: 'What-if', icon: 'whatif' },
    { id: 'decide/goals', label: 'Goals', icon: 'goals' },
  ] },
  { title: 'Monitor', items: [
    { id: 'monitor/forecast', label: 'Forecast', icon: 'forecast' },
    { id: 'monitor/predict', label: 'Predict', icon: 'predict' },
    { id: 'monitor/progress', label: 'Progress', icon: 'progress' },
    { id: 'monitor/alerts', label: 'Alerts', icon: 'alerts' },
  ] },
  { title: 'More', items: [
    { id: 'explore', label: 'Explore', icon: 'explore' },
    { id: 'guide', label: 'Guide', icon: 'guide' },
    { id: 'health', label: 'Data health', icon: 'health' },
  ] },
];

export function Sidebar({ route }) {
  const contract = useContract();
  const name = contract.data ? contract.data.project.name : 'Dashboard';
  return (
    <nav className="sidebar" aria-label="Main">
      <p className="sidebar-brand">{name}</p>
      {NAV_GROUPS.map(group => (
        <div className="sidebar-group" key={group.title}>
          <p className="sidebar-title">{group.title}</p>
          <ul>
            {group.items.map(item => (
              <li key={item.id}>
                <a className={'sidebar-link' + (item.id === route ? ' active' : '')} href={'#/' + item.id} aria-current={item.id === route ? 'page' : undefined}>
                  <Icon name={item.icon} />
                  <span>{item.label}</span>
                </a>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </nav>
  );
}
"""

FILES["src/components/shared/Header.jsx"] = r"""import { useContract } from '../../hooks/useContract.js';
import { useDataset } from '../../hooks/useDataset.js';
import { useFormat } from '../../context/FormatContext.jsx';
import { ThemeToggle } from './ThemeToggle.jsx';

export function Header() {
  const contract = useContract();
  const summary = useDataset('summary');
  const fmt = useFormat();
  const name = contract.data ? contract.data.project.name : 'Dashboard';
  const when = summary.data && summary.data.lastRun ? summary.data.lastRun : (contract.data ? contract.data.generatedAt : '');
  return (
    <header className="topbar">
      <div>
        <p className="topbar-name">{name}</p>
        {when ? <p className="muted small">{'Updated ' + fmt.ago(when)}</p> : null}
      </div>
      <ThemeToggle />
    </header>
  );
}
"""
FILES["src/components/understand/KPICards.jsx"] = r"""import { useDataset } from '../../hooks/useDataset.js';
import { useFormat } from '../../context/FormatContext.jsx';
import { DataState } from '../shared/DataState.jsx';
import { SkeletonCard } from '../shared/SkeletonCard.jsx';
import { Icon } from '../shared/Icon.jsx';

export function KPICards() {
  const query = useDataset('kpis');
  const fmt = useFormat();
  if (query.loading || query.error) {
    return <DataState query={query} label="key numbers" skeleton={<SkeletonCard count={4} height={112} />} />;
  }
  const items = query.data;
  return (
    <div className="grid kpi-grid">
      {items.map(k => (
        <article className="card kpi" key={k.key}>
          <p className="kpi-label">{k.label}</p>
          <p className="kpi-value">{fmt.value(k.value, k.format)}</p>
          {k.trend !== null ? (
            <p className="kpi-trend">
              <Icon name={k.trend > 0 ? 'up' : k.trend < 0 ? 'down' : 'flat'} />
              <span>{(k.trend > 0 ? '+' : '') + fmt.value(k.trend, 'percent') + ' vs previous period'}</span>
            </p>
          ) : null}
          {k.note ? <p className="muted small">{k.note}</p> : null}
        </article>
      ))}
    </div>
  );
}
"""

FILES["src/components/understand/ChartPanel.jsx"] = r"""import {
  ResponsiveContainer, BarChart, Bar, LineChart, Line, ScatterChart, Scatter,
  XAxis, YAxis, CartesianGrid, Tooltip, PieChart, Pie, Cell, Legend,
} from 'recharts';
import { useChartColors } from '../../hooks/useChartColors.js';
import { useFormat } from '../../context/FormatContext.jsx';
import { truncate } from '../../utils/text.js';

function tipStyle(colors) {
  return { background: colors.surface, border: '1px solid ' + colors.grid, color: colors.textPrimary, borderRadius: '0.5rem' };
}

function tickProps(colors) {
  return { fill: colors.text, fontSize: 12 };
}

export function BarBlock({ rows, selected, onSelect, format, histogram, name }) {
  const colors = useChartColors();
  const fmt = useFormat();
  const long = !histogram && rows.some(r => String(r.label).length > 14);
  const pick = d => {
    const label = d && d.payload ? d.payload.label : d && d.label;
    if (onSelect && label !== undefined) onSelect(label);
  };
  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={rows} layout={long ? 'vertical' : 'horizontal'} barCategoryGap={histogram ? 0 : '20%'} margin={{ top: 8, right: 16, bottom: 8, left: 8 }}>
        <CartesianGrid stroke={colors.grid} strokeDasharray="3 3" />
        {long ? (
          <XAxis type="number" tickFormatter={fmt.compact} tick={tickProps(colors)} stroke={colors.grid} />
        ) : (
          <XAxis dataKey="label" tickFormatter={v => truncate(v, 14)} tick={tickProps(colors)} stroke={colors.grid} interval="preserveStartEnd" minTickGap={8} />
        )}
        {long ? (
          <YAxis type="category" dataKey="label" width={120} tickFormatter={v => truncate(v, 14)} tick={tickProps(colors)} stroke={colors.grid} />
        ) : (
          <YAxis tickFormatter={fmt.compact} tick={tickProps(colors)} stroke={colors.grid} />
        )}
        <Tooltip contentStyle={tipStyle(colors)} cursor={{ fill: colors.grid, fillOpacity: 0.4 }} formatter={v => [fmt.value(v, format || 'decimal'), name || 'Value']} />
        <Bar dataKey="value" onClick={pick} cursor={onSelect ? 'pointer' : 'default'} isAnimationActive={false}>
          {rows.map((r, i) => (
            <Cell key={String(r.label) + '-' + i} fill={colors.series[0]} fillOpacity={selected && selected !== r.label ? 0.35 : 1} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

export function LineBlock({ rows, format, name }) {
  const colors = useChartColors();
  const fmt = useFormat();
  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={rows} margin={{ top: 8, right: 16, bottom: 8, left: 8 }}>
        <CartesianGrid stroke={colors.grid} strokeDasharray="3 3" />
        <XAxis dataKey="label" tickFormatter={v => truncate(v, 14)} tick={tickProps(colors)} stroke={colors.grid} interval="preserveStartEnd" minTickGap={16} />
        <YAxis tickFormatter={fmt.compact} tick={tickProps(colors)} stroke={colors.grid} />
        <Tooltip contentStyle={tipStyle(colors)} formatter={v => [fmt.value(v, format || 'decimal'), name || 'Value']} />
        <Line type="monotone" dataKey="value" stroke={colors.series[0]} strokeWidth={2} dot={rows.length <= 60} isAnimationActive={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}

function ScatterBlock({ chart }) {
  const colors = useChartColors();
  const fmt = useFormat();
  return (
    <ResponsiveContainer width="100%" height="100%">
      <ScatterChart margin={{ top: 8, right: 16, bottom: 8, left: 8 }}>
        <CartesianGrid stroke={colors.grid} strokeDasharray="3 3" />
        <XAxis type="number" dataKey="x" name={chart.xLabel || 'x'} tickFormatter={fmt.compact} tick={tickProps(colors)} stroke={colors.grid} />
        <YAxis type="number" dataKey="y" name={chart.yLabel || 'y'} tickFormatter={fmt.compact} tick={tickProps(colors)} stroke={colors.grid} />
        <Tooltip contentStyle={tipStyle(colors)} cursor={{ strokeDasharray: '3 3' }} />
        <Scatter data={chart.rows} fill={colors.series[0]} isAnimationActive={false} />
      </ScatterChart>
    </ResponsiveContainer>
  );
}

function PieBlock({ chart }) {
  const colors = useChartColors();
  const fmt = useFormat();
  return (
    <ResponsiveContainer width="100%" height="100%">
      <PieChart>
        <Pie data={chart.rows} dataKey="value" nameKey="label" cx="50%" cy="50%" innerRadius={chart.type === 'doughnut' ? 60 : 0} outerRadius={100} isAnimationActive={false}>
          {chart.rows.map((r, i) => (
            <Cell key={r.label + '-' + i} fill={colors.series[i % colors.series.length]} />
          ))}
        </Pie>
        <Tooltip contentStyle={tipStyle(colors)} formatter={v => fmt.value(v, 'decimal')} />
        <Legend />
      </PieChart>
    </ResponsiveContainer>
  );
}

function HeatBlock({ chart }) {
  const fmt = useFormat();
  const rowKeys = [...new Set(chart.rows.map(r => r.row))];
  const colKeys = [...new Set(chart.rows.map(r => r.col))];
  const lookup = new Map(chart.rows.map(r => [r.row + '\u0000' + r.col, r.value]));
  const values = chart.rows.map(r => r.value);
  const lo = Math.min(...values);
  const hi = Math.max(...values);
  const intensity = v => (hi === lo ? 50 : 10 + ((v - lo) / (hi - lo)) * 80);
  return (
    <div className="heat-wrap">
      <div className="heat" style={{ gridTemplateColumns: 'auto repeat(' + colKeys.length + ', minmax(2.5rem, 1fr))' }}>
        <span />
        {colKeys.map(c => <span className="heat-head" key={'c-' + c}>{truncate(c, 10)}</span>)}
        {rowKeys.map(r => (
          <div className="heat-row" key={'r-' + r}>
            <span className="heat-head">{truncate(r, 14)}</span>
            {colKeys.map(c => {
              const v = lookup.get(r + '\u0000' + c);
              return (
                <span
                  className="heat-cell"
                  key={r + '|' + c}
                  title={r + ' / ' + c + ': ' + (v === undefined ? '-' : fmt.value(v, 'decimal'))}
                  style={{ background: v === undefined ? 'transparent' : 'color-mix(in srgb, var(--color-accent) ' + intensity(v) + '%, transparent)' }}
                />
              );
            })}
          </div>
        ))}
      </div>
      <table className="sr-only">
        <caption>{chart.title}</caption>
        <thead><tr><th scope="col">Row</th><th scope="col">Column</th><th scope="col">Value</th></tr></thead>
        <tbody>
          {chart.rows.map(r => (
            <tr key={r.row + '|' + r.col}><td>{r.row}</td><td>{r.col}</td><td>{fmt.value(r.value, 'decimal')}</td></tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ChartBody({ chart, rows }) {
  switch (chart.type) {
    case 'line': return <LineBlock rows={rows} name={chart.yLabel} />;
    case 'histogram': return <BarBlock rows={rows} histogram name={chart.yLabel} />;
    case 'scatter': return <ScatterBlock chart={chart} />;
    case 'heatmap': return <HeatBlock chart={chart} />;
    case 'pie':
    case 'doughnut': return <PieBlock chart={chart} />;
    default: return <BarBlock rows={rows} name={chart.yLabel} />;
  }
}

export function ChartPanel({ chart }) {
  let rows = chart.rows;
  let note = '';
  if (chart.type === 'bar' && rows.length > 40) {
    rows = [...rows].sort((a, b) => b.value - a.value).slice(0, 40);
    note = 'Showing the top 40 of ' + chart.rows.length + ' categories.';
  }
  const axes = chart.xLabel || chart.yLabel ? [chart.yLabel, chart.xLabel].filter(Boolean).join(' by ') : '';
  return (
    <section className="card chart-card">
      <h3>{chart.title}</h3>
      {chart.question ? <p className="muted">{chart.question}</p> : null}
      <div className={chart.type === 'heatmap' ? 'chart-box chart-scroll' : 'chart-box'}>
        <ChartBody chart={chart} rows={rows} />
      </div>
      {axes ? <p className="muted small">{axes}</p> : null}
      {note ? <p className="muted small">{note}</p> : null}
    </section>
  );
}
"""

FILES["src/components/understand/ChartGrid.jsx"] = r"""import { useDataset } from '../../hooks/useDataset.js';
import { DataState } from '../shared/DataState.jsx';
import { SkeletonCard } from '../shared/SkeletonCard.jsx';
import { ErrorBoundary } from '../shared/ErrorBoundary.jsx';
import { ChartPanel } from './ChartPanel.jsx';

export function ChartGrid() {
  const query = useDataset('charts');
  if (query.loading || query.error) {
    return <DataState query={query} label="charts" skeleton={<SkeletonCard count={2} height={352} />} />;
  }
  const charts = query.data;
  return (
    <div className="grid chart-grid">
      {charts.map((chart, i) => (
        <ErrorBoundary key={chart.id + '-' + i} label={chart.title}>
          <ChartPanel chart={chart} />
        </ErrorBoundary>
      ))}
    </div>
  );
}
"""

FILES["src/components/explorer/DrillDownPanel.jsx"] = r"""import { useEffect, useRef } from 'react';
import { Icon } from '../shared/Icon.jsx';

export function DrillDownPanel({ title, onClose, children }) {
  const ref = useRef(null);
  const closeRef = useRef(onClose);
  closeRef.current = onClose;

  useEffect(() => {
    const previous = document.activeElement;
    const node = ref.current;
    if (node) node.focus();
    const onKey = e => {
      if (e.key === 'Escape') { closeRef.current(); return; }
      if (e.key !== 'Tab' || !node) return;
      const items = node.querySelectorAll('button, a[href], input, select, textarea');
      if (items.length === 0) { e.preventDefault(); return; }
      const first = items[0];
      const last = items[items.length - 1];
      if (e.shiftKey && (document.activeElement === first || document.activeElement === node)) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('keydown', onKey);
      if (previous && previous.focus) previous.focus();
    };
  }, []);

  return (
    <div className="drill-backdrop" onClick={() => closeRef.current()}>
      <aside className="drill-panel" role="dialog" aria-modal="true" aria-label={title} tabIndex={-1} ref={ref} onClick={e => e.stopPropagation()}>
        <header className="drill-head">
          <h2>{title}</h2>
          <button type="button" className="icon-btn" onClick={() => closeRef.current()} aria-label="Close details"><Icon name="close" /></button>
        </header>
        <div className="drill-body">{children}</div>
        <p className="muted small">Figures are aggregated; no individual records are shown.</p>
      </aside>
    </div>
  );
}
"""

FILES["src/components/understand/SegmentExplorer.jsx"] = r"""import { useState } from 'react';
import { useDataset } from '../../hooks/useDataset.js';
import { useFormat } from '../../context/FormatContext.jsx';
import { DataState } from '../shared/DataState.jsx';
import { SkeletonCard } from '../shared/SkeletonCard.jsx';
import { DrillDownPanel } from '../explorer/DrillDownPanel.jsx';
import { BarBlock } from './ChartPanel.jsx';
import { humanize } from '../../utils/adapters.js';

export function SegmentExplorer() {
  const query = useDataset('segments');
  if (query.loading || query.error) {
    return <DataState query={query} label="segments" skeleton={<SkeletonCard count={3} height={140} />} />;
  }
  return <SegmentBody segments={query.data} />;
}

function SegmentBody({ segments }) {
  const fmt = useFormat();
  const [open, setOpen] = useState(null);
  const chosen = segments.items.find(s => s.name === open) || null;
  const sizeRows = segments.items.map(s => ({ label: s.name, value: s.size }));
  return (
    <div className="stack">
      {segments.method ? <p className="muted">{'Method: ' + segments.method}</p> : null}
      <div className="grid">
        {segments.items.map(s => (
          <button type="button" className="card segment-card" key={s.name} onClick={() => setOpen(s.name)}>
            <span className="segment-name">{s.name}</span>
            <span className="kpi-value">{fmt.value(s.size, 'integer')}</span>
            <span className="bar-track" aria-hidden="true"><span className="bar-fill" style={{ width: Math.min(100, Math.max(0, s.share)) + '%' }} /></span>
            <span className="muted small">{fmt.value(s.share, 'percent') + ' of the total'}</span>
          </button>
        ))}
      </div>
      <section className="card chart-card">
        <h3>Segment sizes</h3>
        <div className="chart-box"><BarBlock rows={sizeRows} format="integer" name="Size" /></div>
      </section>
      {chosen ? (
        <DrillDownPanel title={chosen.name} onClose={() => setOpen(null)}>
          {chosen.description ? <p>{chosen.description}</p> : null}
          <dl className="detail-list">
            <dt>Size</dt><dd>{fmt.value(chosen.size, 'integer')}</dd>
            <dt>Share</dt><dd>{fmt.value(chosen.share, 'percent')}</dd>
            {Object.entries(chosen.summary).map(([k, v]) => (
              <div className="detail-pair" key={k}><dt>{humanize(k)}</dt><dd>{fmt.value(v, 'decimal')}</dd></div>
            ))}
          </dl>
        </DrillDownPanel>
      ) : null}
    </div>
  );
}
"""

FILES["src/components/understand/AnomalyTable.jsx"] = r"""import { useMemo, useState } from 'react';
import { useDataset } from '../../hooks/useDataset.js';
import { useFormat } from '../../context/FormatContext.jsx';
import { DataState } from '../shared/DataState.jsx';
import { SkeletonCard } from '../shared/SkeletonCard.jsx';

const COLUMNS = [
  { key: 'date', label: 'Date' },
  { key: 'metric', label: 'Metric' },
  { key: 'value', label: 'Value' },
  { key: 'expected', label: 'Expected' },
  { key: 'score', label: 'Score' },
  { key: 'reason', label: 'Reason' },
];
const PAGE = 25;

export function AnomalyTable() {
  const query = useDataset('anomalies');
  if (query.loading || query.error) {
    return <DataState query={query} label="anomalies" skeleton={<SkeletonCard count={2} height={160} />} />;
  }
  return <AnomalyBody data={query.data} />;
}

function AnomalyBody({ data }) {
  const fmt = useFormat();
  const [sort, setSort] = useState({ key: 'score', dir: 'desc' });
  const [page, setPage] = useState(0);
  const sorted = useMemo(() => {
    const rows = [...data.items];
    rows.sort((a, b) => {
      const x = a[sort.key];
      const y = b[sort.key];
      if (x === null && y === null) return 0;
      if (x === null) return 1;
      if (y === null) return -1;
      const cmp = typeof x === 'number' && typeof y === 'number' ? x - y : String(x).localeCompare(String(y));
      return sort.dir === 'asc' ? cmp : -cmp;
    });
    return rows;
  }, [data, sort]);
  const pages = Math.max(1, Math.ceil(sorted.length / PAGE));
  const current = Math.min(page, pages - 1);
  const shown = sorted.slice(current * PAGE, current * PAGE + PAGE);
  const show = (row, key) => {
    const v = row[key];
    if (v === null || v === '') return '-';
    if (key === 'date') return fmt.date(v);
    if (typeof v === 'number') return fmt.value(v, 'decimal');
    return v;
  };
  const toggle = key => {
    setSort(prev => (prev.key === key ? { key, dir: prev.dir === 'asc' ? 'desc' : 'asc' } : { key, dir: 'desc' }));
    setPage(0);
  };
  return (
    <div className="stack">
      <div className="grid">
        <div className="card kpi"><p className="kpi-label">Flagged records</p><p className="kpi-value">{fmt.value(data.total, 'integer')}</p></div>
        <div className="card kpi"><p className="kpi-label">Share flagged</p><p className="kpi-value">{data.rate === null ? '-' : fmt.value(data.rate, 'percent')}</p></div>
      </div>
      {data.method ? <p className="muted">{'Method: ' + data.method}</p> : null}
      {data.items.length === 0 ? <div className="card state-box"><p>No anomalies were flagged.</p></div> : (
        <div className="card table-card">
          <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  {COLUMNS.map(c => (
                    <th key={c.key} scope="col" aria-sort={sort.key === c.key ? (sort.dir === 'asc' ? 'ascending' : 'descending') : 'none'}>
                      <button type="button" className="th-btn" onClick={() => toggle(c.key)}>{c.label + (sort.key === c.key ? (sort.dir === 'asc' ? ' (up)' : ' (down)') : '')}</button>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {shown.map(row => (
                  <tr key={row.id}>
                    {COLUMNS.map(c => <td key={c.key}>{show(row, c.key)}</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="pager">
            <button type="button" className="btn-secondary" disabled={current === 0} onClick={() => setPage(current - 1)}>Previous</button>
            <span className="muted small">{'Page ' + (current + 1) + ' of ' + pages}</span>
            <button type="button" className="btn-secondary" disabled={current >= pages - 1} onClick={() => setPage(current + 1)}>Next</button>
          </div>
        </div>
      )}
    </div>
  );
}
"""
FILES["src/components/decide/InsightCards.jsx"] = r"""import { useState } from 'react';
import { useDataset } from '../../hooks/useDataset.js';
import { DataState } from '../shared/DataState.jsx';
import { SkeletonCard } from '../shared/SkeletonCard.jsx';
import { SeverityBadge } from '../shared/SeverityBadge.jsx';

const CHIPS = [['ALL', 'All'], ['HIGH', 'High'], ['MEDIUM', 'Medium'], ['LOW', 'Low']];

export function InsightCards() {
  const query = useDataset('insights');
  if (query.loading || query.error) {
    return <DataState query={query} label="insights" skeleton={<SkeletonCard count={3} height={140} />} />;
  }
  return <InsightBody items={query.data} />;
}

function InsightBody({ items }) {
  const [filter, setFilter] = useState('ALL');
  const count = key => (key === 'ALL' ? items.length : items.filter(i => i.severity === key).length);
  const shown = filter === 'ALL' ? items : items.filter(i => i.severity === filter);
  return (
    <div className="stack">
      <div className="chips" role="group" aria-label="Filter by severity">
        {CHIPS.map(([key, label]) => (
          <button type="button" key={key} className={'chip' + (filter === key ? ' active' : '')} aria-pressed={filter === key} onClick={() => setFilter(key)}>
            {label + ' (' + count(key) + ')'}
          </button>
        ))}
      </div>
      {shown.length === 0 ? <div className="card state-box"><p>No insights match this filter.</p></div> : null}
      <div className="grid wide">
        {shown.map(i => (
          <article className="card insight" key={i.id}>
            <header className="card-head">
              <SeverityBadge severity={i.severity} />
              <span className="muted small">{i.category}</span>
            </header>
            <h3>{i.finding}</h3>
            {i.evidence ? <p className="muted">{i.evidence}</p> : null}
            {i.action ? (
              <div className="callout">
                <p className="callout-title">What to do this week</p>
                <p>{i.action}</p>
              </div>
            ) : null}
          </article>
        ))}
      </div>
    </div>
  );
}
"""

FILES["src/components/decide/RecommendationEngine.jsx"] = r"""import { useDataset } from '../../hooks/useDataset.js';
import { DataState } from '../shared/DataState.jsx';
import { SkeletonCard } from '../shared/SkeletonCard.jsx';

const LEVELS = [['P1', 'Urgent'], ['P2', 'High'], ['P3', 'Medium'], ['P4', 'Routine']];

export function RecommendationEngine() {
  const query = useDataset('recommendations');
  if (query.loading || query.error) {
    return <DataState query={query} label="recommendations" skeleton={<SkeletonCard count={3} height={140} />} />;
  }
  const items = query.data;
  if (items.length === 0) return <div className="card state-box"><p>No recommendations right now.</p></div>;
  return (
    <div className="stack">
      {LEVELS.map(([key, name]) => {
        const group = items.filter(i => i.priority === key);
        if (group.length === 0) return null;
        return (
          <section key={key} className="stack">
            <h2 className="group-title">{name + ' (' + group.length + ')'}</h2>
            <div className="grid wide">
              {group.map(r => (
                <article className="card insight" key={r.id}>
                  <h3>{r.title}</h3>
                  {r.action && r.action !== r.title ? <p>{r.action}</p> : null}
                  {r.evidence ? <p className="muted">{r.evidence}</p> : null}
                  {r.impact ? <p><strong>Impact: </strong>{r.impact}</p> : null}
                  {r.when ? <p className="muted small">{'When: ' + r.when}</p> : null}
                </article>
              ))}
            </div>
          </section>
        );
      })}
    </div>
  );
}
"""

FILES["src/components/decide/WhatIfSimulator.jsx"] = r"""import { useId, useState } from 'react';
import { useDataset, useDataFile } from '../../hooks/useDataset.js';
import { useFormat } from '../../context/FormatContext.jsx';
import { DataState } from '../shared/DataState.jsx';
import { SkeletonCard } from '../shared/SkeletonCard.jsx';
import { adaptSimulation } from '../../utils/adapters.js';
import { dataPath } from '../../utils/datasets.js';
import { interpolate } from '../../utils/sim.js';

export function WhatIfSimulator() {
  const query = useDataset('simulations');
  if (query.loading || query.error) {
    return <DataState query={query} label="what-if scenarios" skeleton={<SkeletonCard count={2} height={160} />} />;
  }
  if (query.data.length === 0) return <div className="card state-box"><p>No what-if scenarios were produced for this project.</p></div>;
  return <SimulatorBody index={query.data} />;
}

function SimulatorBody({ index }) {
  const pickerId = useId();
  const [chosen, setChosen] = useState(index[0].id);
  const entry = index.find(i => i.id === chosen) || index[0];
  return (
    <div className="stack">
      <div className="field">
        <label htmlFor={pickerId}>Scenario</label>
        <select id={pickerId} value={entry.id} onChange={e => setChosen(e.target.value)}>
          {index.map(i => <option key={i.id} value={i.id}>{i.title}</option>)}
        </select>
      </div>
      <SimulationView key={entry.id} entry={entry} />
    </div>
  );
}

function SimulationView({ entry }) {
  const query = useDataFile(dataPath(entry.file), adaptSimulation);
  if (query.loading || query.error) {
    return <DataState query={query} label="scenario" skeleton={<SkeletonCard count={2} height={160} />} />;
  }
  return <SimulationBody sim={query.data} />;
}

function SimulationBody({ sim }) {
  const fmt = useFormat();
  const sliderId = useId();
  const v = sim.variable;
  const [x, setX] = useState(v.default);
  const base = interpolate(sim.table, v.default);
  const scenario = interpolate(sim.table, x);
  const shownX = fmt.value(x, v.format) + (v.unit && v.format !== 'percent' && v.format !== 'currency' ? ' ' + v.unit : '');
  return (
    <div className="stack">
      <section className="card">
        <h3>{sim.title}</h3>
        {sim.description ? <p className="muted">{sim.description}</p> : null}
        <div className="field">
          <label htmlFor={sliderId}>{v.label + ': ' + shownX}</label>
          <input id={sliderId} type="range" min={v.min} max={v.max} step={v.step} value={x} onChange={e => setX(Number(e.target.value))} />
          <p className="muted small">{'Range ' + fmt.value(v.min, v.format) + ' to ' + fmt.value(v.max, v.format) + '. Starting point ' + fmt.value(v.default, v.format) + '.'}</p>
        </div>
        <button type="button" className="btn-secondary" onClick={() => setX(v.default)}>Reset</button>
      </section>
      <div className="card table-card">
        <div className="table-scroll">
          <table className="data-table">
            <thead>
              <tr><th scope="col">Measure</th><th scope="col">Baseline</th><th scope="col">Scenario</th><th scope="col">Difference</th></tr>
            </thead>
            <tbody>
              {sim.outputs.map(o => {
                const b = base ? base[o.key] : null;
                const s = scenario ? scenario[o.key] : null;
                const diff = b !== null && b !== undefined && s !== null && s !== undefined ? s - b : null;
                return (
                  <tr key={o.key}>
                    <th scope="row">{o.label}</th>
                    <td>{fmt.value(b, o.format)}</td>
                    <td>{fmt.value(s, o.format)}</td>
                    <td>{diff === null ? '-' : (diff > 0 ? '+' : '') + fmt.value(diff, o.format)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
      {sim.assumptions.length > 0 ? (
        <section className="card">
          <h3>Assumptions</h3>
          <ul className="plain-list">
            {sim.assumptions.map((a, i) => <li key={'a-' + i}>{a}</li>)}
          </ul>
        </section>
      ) : null}
    </div>
  );
}
"""

FILES["src/components/decide/GoalTracker.jsx"] = r"""import { useEffect, useState } from 'react';
import { useDataset } from '../../hooks/useDataset.js';
import { useContract } from '../../hooks/useContract.js';
import { useFormat } from '../../context/FormatContext.jsx';
import { DataState } from '../shared/DataState.jsx';
import { SkeletonCard } from '../shared/SkeletonCard.jsx';
import { formatKind } from '../../utils/formatters.js';

function readSaved(clientId) {
  try { return JSON.parse(localStorage.getItem('goals:' + clientId) || '{}'); } catch { return {}; }
}

function writeSaved(clientId, values) {
  try { localStorage.setItem('goals:' + clientId, JSON.stringify(values)); } catch { /* storage may be blocked; the entry stays on screen only */ }
}

export function GoalTracker() {
  const goals = useDataset('goals');
  const progress = useDataset('goalProgress');
  const contract = useContract();
  if (goals.loading || goals.error) {
    return <DataState query={goals} label="goals" skeleton={<SkeletonCard count={3} height={120} />} />;
  }
  const clientId = contract.data ? contract.data.project.clientId : 'project';
  return <GoalBody goals={goals.data} actuals={progress.data || []} clientId={clientId} />;
}

function GoalBody({ goals, actuals, clientId }) {
  const fmt = useFormat();
  const [saved, setSaved] = useState({});
  useEffect(() => { setSaved(readSaved(clientId)); }, [clientId]);
  const update = (key, value) => {
    const next = { ...saved, [key]: value };
    setSaved(next);
    writeSaved(clientId, next);
  };
  if (goals.length === 0) return <div className="card state-box"><p>No goals are configured for this project.</p></div>;
  return (
    <div className="grid wide">
      {goals.map(g => {
        const row = actuals.find(a => a.key === g.key);
        const entered = saved[g.key] === undefined || saved[g.key] === '' ? null : Number(saved[g.key]);
        const target = g.clientSets ? (entered !== null && Number.isFinite(entered) ? entered : null) : g.target;
        const kind = formatKind(g.unit);
        const actual = row ? row.actual : null;
        const pct = target && actual !== null && actual !== undefined ? (actual / target) * 100 : (row ? row.pct : null);
        const inputId = 'goal-' + g.key;
        return (
          <article className="card" key={g.key}>
            <h3>{g.label}</h3>
            {g.description ? <p className="muted">{g.description}</p> : null}
            {g.clientSets ? (
              <div className="field">
                <label htmlFor={inputId}>{'Your target' + (g.unit ? ' (' + g.unit + ')' : '')}</label>
                <input id={inputId} type="number" inputMode="decimal" value={saved[g.key] === undefined ? '' : saved[g.key]} onChange={e => update(g.key, e.target.value)} />
                <p className="muted small">Saved on this device only</p>
              </div>
            ) : (
              <p><strong>Target: </strong>{target === null ? 'not set' : fmt.value(target, kind)}</p>
            )}
            {actual !== null && actual !== undefined ? <p><strong>Actual: </strong>{fmt.value(actual, kind)}</p> : null}
            {pct !== null && pct !== undefined ? (
              <div>
                <span className="bar-track" aria-hidden="true"><span className="bar-fill" style={{ width: Math.min(100, Math.max(0, pct)) + '%' }} /></span>
                <p className="muted small">{fmt.value(pct, 'percent') + ' of target'}</p>
              </div>
            ) : null}
          </article>
        );
      })}
    </div>
  );
}
"""

FILES["src/components/monitor/Forecaster.jsx"] = r"""import { useMemo } from 'react';
import {
  ResponsiveContainer, ComposedChart, Line, Area, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
} from 'recharts';
import { useDataset } from '../../hooks/useDataset.js';
import { useFormat } from '../../context/FormatContext.jsx';
import { useChartColors } from '../../hooks/useChartColors.js';
import { DataState } from '../shared/DataState.jsx';
import { SkeletonCard } from '../shared/SkeletonCard.jsx';
import { formatKind } from '../../utils/formatters.js';
import { truncate } from '../../utils/text.js';

export function Forecaster() {
  const query = useDataset('forecast');
  if (query.loading || query.error) {
    return <DataState query={query} label="forecast" skeleton={<SkeletonCard count={2} height={320} />} />;
  }
  return <ForecastBody f={query.data} />;
}

function ForecastBody({ f }) {
  const fmt = useFormat();
  const colors = useChartColors();
  const kind = formatKind(f.unit);
  const rows = useMemo(() => {
    const hist = f.history.map(r => ({ t: r.t, history: r.value }));
    const fut = f.forecast.map(r => ({
      t: r.t, forecast: r.value, low: r.low, band: r.low !== null && r.high !== null ? r.high - r.low : null,
    }));
    return [...hist, ...fut];
  }, [f]);
  const hasBand = f.forecast.some(r => r.low !== null && r.high !== null);
  const tip = { background: colors.surface, border: '1px solid ' + colors.grid, color: colors.textPrimary, borderRadius: '0.5rem' };
  const tick = { fill: colors.text, fontSize: 12 };
  return (
    <div className="stack">
      <section className="card chart-card">
        <h3>{f.metric ? 'Forecast: ' + f.metric : 'Forecast'}</h3>
        <p className="muted">{[f.horizon ? 'Horizon: ' + f.horizon : '', f.method ? 'Method: ' + f.method : ''].filter(Boolean).join('. ')}</p>
        <div className="chart-box">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={rows} margin={{ top: 8, right: 16, bottom: 8, left: 8 }}>
              <CartesianGrid stroke={colors.grid} strokeDasharray="3 3" />
              <XAxis dataKey="t" tickFormatter={v => truncate(v, 12)} tick={tick} stroke={colors.grid} interval="preserveStartEnd" minTickGap={16} />
              <YAxis tickFormatter={fmt.compact} tick={tick} stroke={colors.grid} />
              <Tooltip contentStyle={tip} formatter={v => fmt.value(v, kind)} />
              <Legend />
              {hasBand ? <Area type="monotone" dataKey="low" stackId="band" stroke="none" fill="transparent" legendType="none" tooltipType="none" isAnimationActive={false} connectNulls={false} /> : null}
              {hasBand ? <Area type="monotone" dataKey="band" stackId="band" stroke="none" fill={colors.series[0]} fillOpacity={0.18} legendType="none" tooltipType="none" isAnimationActive={false} connectNulls={false} /> : null}
              <Line type="monotone" dataKey="history" name="History" stroke={colors.series[0]} strokeWidth={2} dot={false} connectNulls={false} isAnimationActive={false} />
              <Line type="monotone" dataKey="forecast" name="Forecast" stroke={colors.series[1]} strokeWidth={2} strokeDasharray="6 4" dot={false} connectNulls={false} isAnimationActive={false} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
        <p className="muted small">This is a forecast, not a guarantee.</p>
        <p><a href="#/monitor/predict">Try your own numbers on the Predict page</a></p>
      </section>
      <div className="grid">
        {f.error ? (
          <article className="card kpi">
            <p className="kpi-label">How far off it was on recent history</p>
            <p className="kpi-value">{f.error.mape !== null ? fmt.value(f.error.mape, 'percent') : (f.error.mae !== null ? fmt.value(f.error.mae, kind) : '-')}</p>
            <p className="muted small">
              {[
                f.error.mae !== null ? 'Average miss: ' + fmt.value(f.error.mae, kind) : '',
                f.error.baselineMae !== null ? 'Simple baseline miss: ' + fmt.value(f.error.baselineMae, kind) : '',
                f.error.period ? 'Tested on ' + f.error.period : '',
              ].filter(Boolean).join('. ')}
            </p>
          </article>
        ) : null}
        {f.note ? <article className="card"><p>{f.note}</p></article> : null}
      </div>
    </div>
  );
}
"""

FILES["src/components/monitor/Predictor.jsx"] = r"""import { useId, useMemo, useState } from 'react';
import { useDataset } from '../../hooks/useDataset.js';
import { useContract } from '../../hooks/useContract.js';
import { useFormat } from '../../context/FormatContext.jsx';
import { SkeletonCard } from '../shared/SkeletonCard.jsx';
import { humanize } from '../../utils/adapters.js';
import { refreshHint } from '../../utils/text.js';
import { formatKind } from '../../utils/formatters.js';
import { defaultsFor, validateInputs, predict, lookupAt, forecastAt } from '../../utils/predict.js';

export function Predictor() {
  const scorer = useDataset('scorer');
  const lookup = useDataset('forecastLookup');
  const forecast = useDataset('forecast');
  const contract = useContract();

  if (scorer.loading || lookup.loading || forecast.loading) return <SkeletonCard count={2} height={160} />;
  if (scorer.data) return <ModelPredictor scorer={scorer.data} />;
  if (lookup.data) return <LookupPredictor lookup={lookup.data} />;
  if (forecast.data && forecast.data.forecast.length > 0) return <HorizonPredictor forecast={forecast.data} />;
  const reasons = [['Scoring file', scorer.error], ['Lookup file', lookup.error], ['Forecast file', forecast.error]]
    .filter(([, error]) => error)
    .map(([name, error]) => name + ': ' + error.message);
  return <UnavailablePredictor contract={contract.data} reasons={reasons} />;
}

function ModelPredictor({ scorer }) {
  const fmt = useFormat();
  const baseId = useId();
  const [values, setValues] = useState(() => defaultsFor(scorer.fields));
  const [result, setResult] = useState(null);
  const check = useMemo(() => validateInputs(scorer.fields, values), [scorer, values]);

  const setField = (key, value) => {
    setValues(prev => ({ ...prev, [key]: value }));
    setResult(null);
  };
  const onSubmit = event => {
    event.preventDefault();
    if (check.problems.length > 0) return;
    const prepared = {};
    for (const f of scorer.fields) prepared[f.key] = f.type === 'number' ? Number(values[f.key]) : values[f.key];
    setResult(predict(scorer, prepared));
  };
  const onReset = () => {
    setValues(defaultsFor(scorer.fields));
    setResult(null);
  };
  const labelOf = key => {
    const found = scorer.fields.find(f => f.key === key);
    return found ? found.label : key;
  };

  return (
    <section className="card predictor">
      <header>
        <h2>{scorer.target.label}</h2>
        <p className="muted">Enter the details below and press Predict.</p>
      </header>
      <form className="predictor-form" onSubmit={onSubmit} noValidate>
        <div className="field-grid">
          {scorer.fields.map(field => {
            const id = baseId + '-' + field.key;
            const warning = check.warnings.find(w => w.key === field.key);
            return (
              <div className="field" key={field.key}>
                <label htmlFor={id}>{field.unit ? field.label + ' (' + field.unit + ')' : field.label}</label>
                {field.type === 'number' ? (
                  <input id={id} type="number" inputMode="decimal" value={values[field.key]}
                    min={field.min === null ? undefined : field.min} max={field.max === null ? undefined : field.max}
                    step={field.step} onChange={e => setField(field.key, e.target.value)} />
                ) : (
                  <select id={id} value={values[field.key]} onChange={e => setField(field.key, e.target.value)}>
                    {field.options.map(option => <option key={option} value={option}>{option}</option>)}
                  </select>
                )}
                {field.help ? <p className="field-help">{field.help}</p> : null}
                {warning ? <p className="field-warning">{warning.message}</p> : null}
              </div>
            );
          })}
        </div>
        {check.problems.length > 0 ? <p className="field-error" role="alert">{check.problems[0].message}</p> : null}
        <div className="form-actions">
          <button type="submit" className="btn-primary" disabled={check.problems.length > 0}>Predict</button>
          <button type="button" className="btn-secondary" onClick={onReset}>Reset</button>
        </div>
      </form>
      <div className="predictor-result" aria-live="polite">
        {result === null ? (
          <p className="muted">Your result will appear here.</p>
        ) : (
          <div>
            <p className="result-value">{fmt.value(result.value, scorer.target.format)}</p>
            {result.label ? <p className="result-label">{'Risk level: ' + result.label}</p> : null}
            {result.low !== null && result.high !== null ? (
              <p className="muted">{'Typical range ' + fmt.value(result.low, scorer.target.format) + ' to ' + fmt.value(result.high, scorer.target.format)}</p>
            ) : null}
            {result.neighbors !== null ? <p className="muted">{'Based on ' + result.neighbors + ' similar records.'}</p> : null}
            {result.drivers.length > 0 ? (
              <ul className="driver-list">
                {result.drivers.filter(d => d.contribution !== 0).map(d => (
                  <li key={d.field}>{labelOf(d.field) + (d.contribution > 0 ? ' raises this estimate' : ' lowers this estimate')}</li>
                ))}
              </ul>
            ) : null}
            {scorer.fidelity && scorer.fidelity.quality === 'low' ? <p className="field-warning">This estimate is rough for this project.</p> : null}
          </div>
        )}
      </div>
    </section>
  );
}

function LookupPredictor({ lookup }) {
  const fmt = useFormat();
  const id = useId();
  const [input, setInput] = useState('');
  const [result, setResult] = useState(null);
  const valid = input !== '' && Number.isFinite(Number(input));
  const first = lookup.table[0].x;
  const last = lookup.table[lookup.table.length - 1].x;

  const onSubmit = event => {
    event.preventDefault();
    if (valid) setResult(lookupAt(lookup.table, Number(input)));
  };
  const onChange = event => {
    setInput(event.target.value);
    setResult(null);
  };

  return (
    <section className="card predictor">
      <header>
        <h2>{lookup.outputLabel}</h2>
        <p className="muted">Enter a value and press Predict.</p>
      </header>
      <form className="predictor-form" onSubmit={onSubmit} noValidate>
        <div className="field-grid">
          <div className="field">
            <label htmlFor={id}>{lookup.inputLabel}</label>
            <input id={id} type="number" inputMode="decimal" value={input} onChange={onChange} />
            <p className="field-help">{'Values between ' + first + ' and ' + last + ' are covered.'}</p>
          </div>
        </div>
        {input !== '' && !valid ? <p className="field-error" role="alert">{lookup.inputLabel + ' needs a number'}</p> : null}
        <div className="form-actions">
          <button type="submit" className="btn-primary" disabled={!valid}>Predict</button>
          <button type="button" className="btn-secondary" onClick={() => { setInput(''); setResult(null); }}>Reset</button>
        </div>
      </form>
      <div className="predictor-result" aria-live="polite">
        {result === null ? (
          <p className="muted">Your result will appear here.</p>
        ) : (
          <div>
            <p className="result-value">{fmt.value(result.value, 'decimal')}</p>
            {result.low !== null && result.high !== null ? (
              <p className="muted">{'Typical range ' + fmt.value(result.low, 'decimal') + ' to ' + fmt.value(result.high, 'decimal')}</p>
            ) : null}
            {result.outside ? <p className="field-warning">This value is outside the range the analysis covers.</p> : null}
          </div>
        )}
      </div>
    </section>
  );
}

function HorizonPredictor({ forecast }) {
  const fmt = useFormat();
  const id = useId();
  const periods = forecast.forecast.map(row => String(row.t));
  const [period, setPeriod] = useState(periods[0]);
  const [result, setResult] = useState(null);
  const format = formatKind(forecast.unit);

  const onSubmit = event => {
    event.preventDefault();
    setResult(forecastAt(forecast, period));
  };

  return (
    <section className="card predictor">
      <header>
        <h2>{forecast.metric ? 'Forecast: ' + forecast.metric : 'Forecast'}</h2>
        <p className="muted">Choose a future period and press Predict.</p>
      </header>
      <form className="predictor-form" onSubmit={onSubmit} noValidate>
        <div className="field-grid">
          <div className="field">
            <label htmlFor={id}>Period</label>
            <select id={id} value={period} onChange={e => { setPeriod(e.target.value); setResult(null); }}>
              {periods.map(p => <option key={p} value={p}>{p}</option>)}
            </select>
          </div>
        </div>
        <div className="form-actions">
          <button type="submit" className="btn-primary">Predict</button>
          <button type="button" className="btn-secondary" onClick={() => { setPeriod(periods[0]); setResult(null); }}>Reset</button>
        </div>
      </form>
      <div className="predictor-result" aria-live="polite">
        {result === null ? (
          <p className="muted">Your result will appear here.</p>
        ) : (
          <div>
            <p className="result-value">{fmt.value(result.value, format)}</p>
            {result.low !== null && result.high !== null ? (
              <p className="muted">{'Typical range ' + fmt.value(result.low, format) + ' to ' + fmt.value(result.high, format)}</p>
            ) : null}
            {forecast.error && forecast.error.mape !== null ? (
              <p className="muted">{'Typical error on recent history: ' + fmt.value(forecast.error.mape, 'percent')}</p>
            ) : null}
            <p className="muted">This is a forecast, not a guarantee.</p>
          </div>
        )}
      </div>
    </section>
  );
}

function UnavailablePredictor({ contract, reasons }) {
  const baseId = useId();
  let schema = contract && contract.forecaster && Array.isArray(contract.forecaster.input_schema) ? contract.forecaster.input_schema : [];
  if (schema.length === 0 && contract && contract.model && Array.isArray(contract.model.input_fields)) {
    schema = contract.model.input_fields.map(name => ({ name }));
  }
  return (
    <section className="card predictor">
      <header>
        <h2>Prediction</h2>
        <p className="muted">
          {'The analysis did not produce a prediction model for this project, or its scoring file is missing. ' + refreshHint()}
        </p>
      </header>
      {reasons.length > 0 ? (
        <ul className="driver-list">
          {reasons.map(reason => <li key={reason}>{reason}</li>)}
        </ul>
      ) : null}
      <form className="predictor-form" onSubmit={event => event.preventDefault()} noValidate>
        <div className="field-grid">
          {schema.map(item => {
            const id = baseId + '-' + String(item.name);
            return (
              <div className="field" key={String(item.name)}>
                <label htmlFor={id}>{humanize(item.name)}</label>
                <input id={id} type="text" disabled placeholder={Array.isArray(item.range) && item.range.length === 2 ? item.range[0] + ' to ' + item.range[1] : ''} />
              </div>
            );
          })}
        </div>
        <div className="form-actions">
          <button type="submit" className="btn-primary" disabled aria-disabled="true">Predict</button>
        </div>
      </form>
    </section>
  );
}
"""

FILES["src/components/monitor/GoalProgress.jsx"] = r"""import { useDataset } from '../../hooks/useDataset.js';
import { useFormat } from '../../context/FormatContext.jsx';
import { DataState } from '../shared/DataState.jsx';
import { SkeletonCard } from '../shared/SkeletonCard.jsx';
import { formatKind } from '../../utils/formatters.js';

const STATUS = {
  on_track: ['On track', 'status-ok'],
  at_risk: ['At risk', 'status-warn'],
  off_track: ['Off track', 'status-bad'],
  no_target: ['No target', 'status-none'],
};

export function GoalProgress() {
  const query = useDataset('goalProgress');
  const fmt = useFormat();
  if (query.loading || query.error) {
    return <DataState query={query} label="goal progress" skeleton={<SkeletonCard count={3} height={120} />} />;
  }
  const items = query.data;
  if (items.length === 0) return <div className="card state-box"><p>No goals to track yet.</p></div>;
  return (
    <div className="grid wide">
      {items.map(g => {
        const [word, cls] = STATUS[g.status] || STATUS.no_target;
        const kind = formatKind(g.unit);
        return (
          <article className="card" key={g.key}>
            <header className="card-head"><h3>{g.label}</h3><span className={'status ' + cls}>{word}</span></header>
            <p><strong>Actual: </strong>{fmt.value(g.actual, kind)}</p>
            <p><strong>Target: </strong>{g.target === null ? 'not set' : fmt.value(g.target, kind)}</p>
            {g.pct !== null ? (
              <div>
                <span className="bar-track" aria-hidden="true"><span className="bar-fill" style={{ width: Math.min(100, Math.max(0, g.pct)) + '%' }} /></span>
                <p className="muted small">{fmt.value(g.pct, 'percent') + ' of target'}</p>
              </div>
            ) : null}
          </article>
        );
      })}
    </div>
  );
}
"""

FILES["src/components/monitor/AlertCenter.jsx"] = r"""import { useState } from 'react';
import { useDataset } from '../../hooks/useDataset.js';
import { useFormat } from '../../context/FormatContext.jsx';
import { DataState } from '../shared/DataState.jsx';
import { SkeletonCard } from '../shared/SkeletonCard.jsx';
import { SeverityBadge } from '../shared/SeverityBadge.jsx';

const CHIPS = [['ALL', 'All'], ['HIGH', 'High'], ['MEDIUM', 'Medium'], ['LOW', 'Low']];

export function AlertCenter() {
  const query = useDataset('alerts');
  if (query.loading || query.error) {
    return <DataState query={query} label="alerts" skeleton={<SkeletonCard count={2} height={110} />} />;
  }
  return <AlertBody items={query.data} />;
}

function AlertBody({ items }) {
  const fmt = useFormat();
  const [filter, setFilter] = useState('ALL');
  if (items.length === 0) return <div className="card state-box"><p>No active alerts</p></div>;
  const count = key => (key === 'ALL' ? items.length : items.filter(i => i.severity === key).length);
  const shown = filter === 'ALL' ? items : items.filter(i => i.severity === filter);
  return (
    <div className="stack">
      <div className="chips" role="group" aria-label="Filter by severity">
        {CHIPS.map(([key, label]) => (
          <button type="button" key={key} className={'chip' + (filter === key ? ' active' : '')} aria-pressed={filter === key} onClick={() => setFilter(key)}>
            {label + ' (' + count(key) + ')'}
          </button>
        ))}
      </div>
      <div className="grid wide">
        {shown.map(a => (
          <article className="card" key={a.id}>
            <header className="card-head"><SeverityBadge severity={a.severity} />{a.since ? <span className="muted small">{'Since ' + fmt.ago(a.since)}</span> : null}</header>
            <h3>{a.title}</h3>
            {a.message && a.message !== a.title ? <p>{a.message}</p> : null}
            {a.metric ? (
              <p className="muted small">
                {a.metric + (a.value !== null ? ': ' + fmt.value(a.value, 'decimal') : '') + (a.threshold !== null ? ' (threshold ' + fmt.value(a.threshold, 'decimal') + ')' : '')}
              </p>
            ) : null}
          </article>
        ))}
      </div>
    </div>
  );
}
"""
FILES["src/components/explorer/FilterBar.jsx"] = r"""import { useExplorer } from '../../context/ExplorerContext.jsx';

export function FilterBar({ cube, months, metric, onCopy, copyNote }) {
  const { filters, setFilter, clearFilters, setMetricKey, activeCount } = useExplorer();
  return (
    <div className="filter-bar" role="region" aria-label="Filters">
      <label className="filter">
        <span>Metric</span>
        <select value={metric.key} onChange={e => setMetricKey(e.target.value)}>
          {cube.metrics.map(m => <option key={m.key} value={m.key}>{m.label}</option>)}
        </select>
      </label>
      <label className="filter">
        <span>From</span>
        <select value={filters._from || ''} onChange={e => setFilter('_from', e.target.value, false)}>
          <option value="">Start</option>
          {months.map(t => <option key={t} value={t}>{t}</option>)}
        </select>
      </label>
      <label className="filter">
        <span>To</span>
        <select value={filters._to || ''} onChange={e => setFilter('_to', e.target.value, false)}>
          <option value="">End</option>
          {months.map(t => <option key={t} value={t}>{t}</option>)}
        </select>
      </label>
      {cube.dimensions.map(dim => (
        <label className="filter" key={dim.key}>
          <span>{dim.label}</span>
          <select value={filters[dim.key] || ''} onChange={e => setFilter(dim.key, e.target.value, false)}>
            <option value="">All</option>
            {dim.values.map(v => <option key={v} value={v}>{v}</option>)}
          </select>
        </label>
      ))}
      <div className="filter-actions">
        <button type="button" className="btn-secondary" onClick={clearFilters} disabled={activeCount === 0}>{'Clear filters (' + activeCount + ')'}</button>
        <button type="button" className="btn-secondary" onClick={onCopy}>Copy summary</button>
        {copyNote ? <span className="muted small" role="status">{copyNote}</span> : null}
      </div>
    </div>
  );
}
"""

FILES["src/components/explorer/InteractiveExplorer.jsx"] = r"""import { useEffect, useMemo, useState } from 'react';
import { useDataset } from '../../hooks/useDataset.js';
import { useFormat } from '../../context/FormatContext.jsx';
import { useTerm } from '../../context/TerminologyContext.jsx';
import { useExplorer } from '../../context/ExplorerContext.jsx';
import { DataState } from '../shared/DataState.jsx';
import { SkeletonCard } from '../shared/SkeletonCard.jsx';
import { ErrorBoundary } from '../shared/ErrorBoundary.jsx';
import { BarBlock, LineBlock } from '../understand/ChartPanel.jsx';
import { FilterBar } from './FilterBar.jsx';
import { DrillDownPanel } from './DrillDownPanel.jsx';
import { aggregate, totals } from '../../utils/cube.js';

export function InteractiveExplorer() {
  const query = useDataset('explorer');
  if (query.loading || query.error) {
    return <DataState query={query} label="explorer data" skeleton={<SkeletonCard count={3} height={200} />} />;
  }
  return <ExplorerBody cube={query.data} />;
}

function ExplorerBody({ cube }) {
  const fmt = useFormat();
  const term = useTerm();
  const { filters, setFilter, metricKey, setMetricKey } = useExplorer();
  const [drill, setDrill] = useState(null);
  const [tableDim, setTableDim] = useState(cube.dimensions.length ? cube.dimensions[0].key : '');
  const [sort, setSort] = useState({ key: '_label', dir: 'asc' });
  const [copyNote, setCopyNote] = useState('');

  useEffect(() => {
    if (!metricKey || !cube.metrics.some(m => m.key === metricKey)) setMetricKey(cube.metrics[0].key);
  }, [cube, metricKey, setMetricKey]);

  const metric = cube.metrics.find(m => m.key === metricKey) || cube.metrics[0];
  const months = useMemo(() => [...new Set(cube.rows.map(r => r.t))].sort(), [cube]);
  const series = useMemo(() => aggregate(cube, filters, '_time', metric.key), [cube, filters, metric.key]);
  const dims = cube.dimensions.slice(0, 4);
  const metricsShown = cube.metrics.slice(0, 6);

  const tableRows = useMemo(() => {
    if (!tableDim) return [];
    const base = aggregate(cube, filters, tableDim, metric.key);
    const perMetric = {};
    for (const m of metricsShown) perMetric[m.key] = new Map(aggregate(cube, filters, tableDim, m.key).map(r => [r.label, r.value]));
    const rows = base.map(r => ({ label: r.label, values: Object.fromEntries(metricsShown.map(m => [m.key, perMetric[m.key].get(r.label)])) }));
    rows.sort((a, b) => {
      const cmp = sort.key === '_label' ? a.label.localeCompare(b.label) : (a.values[sort.key] || 0) - (b.values[sort.key] || 0);
      return sort.dir === 'asc' ? cmp : -cmp;
    });
    return rows;
  }, [cube, filters, tableDim, metric.key, metricsShown, sort]);

  const onCopy = async () => {
    const lines = ['Filtered summary'];
    const active = Object.entries(filters).filter(([, v]) => v).map(([k, v]) => (k === '_from' ? 'from ' + v : k === '_to' ? 'to ' + v : k + ' = ' + v));
    lines.push(active.length ? 'Filters: ' + active.join(', ') : 'Filters: none');
    for (const m of cube.metrics) lines.push(m.label + ': ' + fmt.value(totals(cube, filters, m.key), m.format));
    try {
      await navigator.clipboard.writeText(lines.join('\n'));
      setCopyNote('Copied');
    } catch {
      setCopyNote('Copy not available');
    }
  };

  const toggleSort = key => setSort(prev => (prev.key === key ? { key, dir: prev.dir === 'asc' ? 'desc' : 'asc' } : { key, dir: 'desc' }));

  let panel = null;
  if (drill) {
    const scope = { ...filters, [drill.dim]: drill.value };
    const other = cube.dimensions.find(d => d.key !== drill.dim);
    const dimLabel = (cube.dimensions.find(d => d.key === drill.dim) || {}).label || drill.dim;
    panel = (
      <DrillDownPanel title={dimLabel + ': ' + drill.value} onClose={() => setDrill(null)}>
        <dl className="detail-list">
          {cube.metrics.map(m => (
            <div className="detail-pair" key={m.key}><dt>{m.label}</dt><dd>{fmt.value(totals(cube, scope, m.key), m.format)}</dd></div>
          ))}
        </dl>
        {other ? (
          <div>
            <h3>{'Top ' + other.label + ' values by ' + metric.label}</h3>
            <ul className="plain-list">
              {aggregate(cube, scope, other.key, metric.key).slice(0, 5).map(r => (
                <li key={r.label}>{r.label + ': ' + fmt.value(r.value, metric.format)}</li>
              ))}
            </ul>
          </div>
        ) : null}
      </DrillDownPanel>
    );
  }

  return (
    <div className="stack">
      <p className="muted">{'Pick a metric, narrow the dates or click a bar to filter every chart. Counts are in ' + term('transaction', { plural: true, lower: true }) + '.'}</p>
      <FilterBar cube={cube} months={months} metric={metric} onCopy={onCopy} copyNote={copyNote} />
      <section className="card chart-card">
        <h3>{metric.label + ' over time'}</h3>
        <div className="chart-box">
          {series.length > 0 ? <LineBlock rows={series} format={metric.format} name={metric.label} /> : <p className="muted">No data for these filters.</p>}
        </div>
      </section>
      <div className="grid chart-grid">
        {dims.map(dim => {
          const rows = aggregate(cube, filters, dim.key, metric.key, dim.key);
          const selected = filters[dim.key] || null;
          return (
            <ErrorBoundary key={dim.key} label={dim.label}>
              <section className="card chart-card">
                <h3>{metric.label + ' by ' + dim.label}</h3>
                <div className="chart-box">
                  {rows.length > 0 ? <BarBlock rows={rows.slice(0, 40)} selected={selected} onSelect={value => setFilter(dim.key, value)} format={metric.format} name={metric.label} /> : <p className="muted">No data for these filters.</p>}
                </div>
                {selected ? <button type="button" className="btn-secondary" onClick={() => setDrill({ dim: dim.key, value: selected })}>{'Details for ' + selected}</button> : null}
              </section>
            </ErrorBoundary>
          );
        })}
      </div>
      {tableDim ? (
        <section className="card table-card">
          <div className="card-head">
            <h3>Top groups</h3>
            <label className="filter">
              <span>Group by</span>
              <select value={tableDim} onChange={e => setTableDim(e.target.value)}>
                {cube.dimensions.map(d => <option key={d.key} value={d.key}>{d.label}</option>)}
              </select>
            </label>
          </div>
          <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th scope="col"><button type="button" className="th-btn" onClick={() => toggleSort('_label')}>Group</button></th>
                  {metricsShown.map(m => <th scope="col" key={m.key}><button type="button" className="th-btn" onClick={() => toggleSort(m.key)}>{m.label}</button></th>)}
                </tr>
              </thead>
              <tbody>
                {tableRows.slice(0, 50).map(r => (
                  <tr key={r.label}>
                    <th scope="row">{r.label}</th>
                    {metricsShown.map(m => <td key={m.key}>{fmt.value(r.values[m.key], m.format)}</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}
      <p className="muted small">Figures are aggregated; no individual records are shown.</p>
      {panel}
    </div>
  );
}
"""

FILES["src/components/manual/GlossaryTable.jsx"] = r"""import { highlightParts } from '../../utils/text.js';

export function Highlight({ text, query }) {
  return (
    <>
      {highlightParts(text, query).map((p, i) => (p.hit ? <mark key={'h-' + i}>{p.text}</mark> : <span key={'h-' + i}>{p.text}</span>))}
    </>
  );
}

export function GlossaryTable({ entries, query }) {
  if (entries.length === 0) return null;
  return (
    <div className="table-scroll">
      <table className="data-table">
        <thead><tr><th scope="col">Term</th><th scope="col">Meaning</th></tr></thead>
        <tbody>
          {entries.map(([term, meaning]) => (
            <tr key={term}>
              <th scope="row"><Highlight text={term} query={query} /></th>
              <td><Highlight text={meaning} query={query} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
"""

FILES["src/components/manual/UserManual.jsx"] = r"""import { useMemo, useState, useId } from 'react';
import { useContract } from '../../hooks/useContract.js';
import { useTerm } from '../../context/TerminologyContext.jsx';
import { GlossaryTable, Highlight } from './GlossaryTable.jsx';

function buildSections(term, project) {
  const revenue = term('revenue', { lower: true });
  const records = term('transaction', { plural: true, lower: true });
  const products = term('product', { plural: true, lower: true });
  const customers = term('customer', { plural: true, lower: true });
  return [
    { id: 'start', title: 'How to use this dashboard', body: [
      'The dashboard has three parts. Understand shows what is happening: key numbers, charts, groups of similar ' + records + ' and unusual records.',
      'Decide turns that into action: findings ranked by importance, a short list of recommended actions, a what-if tool and your goals.',
      'Monitor keeps watch: a forecast, a prediction form, progress against goals and active alerts. Explore lets you slice the numbers yourself, and Data health shows how fresh the data is.',
      'This dashboard covers ' + (project.domain || 'your data') + ', with ' + products + ' and ' + customers + ' as the main groupings and ' + revenue + ' where money is involved.',
    ] },
    { id: 'overview', title: 'Overview', body: [
      'What you see: the key numbers at the top and a set of charts below. Each chart has a title and the question it answers.',
      'What it means: a key number is the latest value of a measure. A small arrow shows the change against the previous period.',
      'What to do: start with the numbers that moved most, then read the chart that explains them.',
    ] },
    { id: 'charts', title: 'How to read the charts', body: [
      'Bar chart: one bar per group; taller means a larger value. Long names are shortened and shown in full when you hover.',
      'Line chart: a value over time; look for direction and sudden jumps.',
      'Histogram: bars show how many records fall in each range, so you can see the usual spread and the extremes.',
      'Scatter chart: each dot is a record; a cloud rising from left to right means the two measures move together.',
      'Heat map: darker cells hold larger values. Hover a cell to read it.',
    ] },
    { id: 'segments', title: 'Segments', body: [
      'What you see: groups of similar ' + records + ', each with a size, a share of the total and a short description.',
      'What it means: members of a group behave alike, so one action usually suits the whole group.',
      'What to do: open a group to see its typical values, then compare it with the others.',
    ] },
    { id: 'anomalies', title: 'Anomalies', body: [
      'What you see: a table of unusual records. An anomaly is an unusual day or record that does not match normal behavior.',
      'What it means: the score shows how unusual it is; a higher score is more unusual. The reason says why it was flagged.',
      'What to do: sort by score, check the top rows first and decide if they are errors or real events.',
    ] },
    { id: 'severity', title: 'Severity and priority levels', body: [
      'High means act soon, Medium means plan for it, Low means keep in mind.',
      'Recommendations use four levels: Urgent, High, Medium and Routine. Start at the top.',
    ] },
    { id: 'insights', title: 'Insights and recommendations', body: [
      'What you see: findings with the evidence behind them and the action to take this week, then a prioritised action list.',
      'What it means: every finding comes from the data in this dashboard; the evidence line shows the numbers.',
      'What to do: filter by severity and work from the most important item down.',
    ] },
    { id: 'whatif', title: 'The what-if tool', body: [
      'What you see: a scenario picker, a slider and a table comparing the baseline with your scenario.',
      'What it means: moving the slider reads along a pre-computed table, so results between points are straight-line estimates.',
      'What to do: try the range end points and note the assumptions listed under the table.',
    ] },
    { id: 'goals', title: 'Goals and progress', body: [
      'Goals can have a fixed target or one you enter yourself. Targets you enter are saved on this device only and are never sent anywhere.',
      'Progress compares the latest actual value with the target and labels it On track, At risk, Off track or No target.',
    ] },
    { id: 'forecast', title: 'Forecast', body: [
      'A forecast is an estimate of the future based on past patterns. The shaded band, when shown, is the likely range.',
      'The typical error is how far off the forecast was when tested on recent history it had not seen. The baseline is a simple rule used as a yardstick; a good forecast beats it.',
      'This is a forecast, not a guarantee.',
    ] },
    { id: 'predict', title: 'Predict', body: [
      'Enter details in the form and press Predict. The estimate is worked out in your browser from patterns in past ' + records + '; nothing you type is stored or sent.',
      'For yes or no outcomes the result is a likelihood from 0 to 100 with a risk level. A caution appears if a value is outside the range seen in the data.',
    ] },
    { id: 'explore', title: 'Explore', body: [
      'Use the filter bar to choose a metric, a date range and groups. Click a bar in any chart to filter every other chart; click it again to clear.',
      'Copy summary puts the filtered totals on your clipboard as plain text.',
      'Figures are aggregated; no individual records are shown.',
    ] },
    { id: 'health', title: 'Data health', body: [
      'This page shows when the analysis last ran, how many rows it used, which steps succeeded and which files are available. If a section is empty, look here first.',
    ] },
  ];
}

const GLOSSARY = [
  ['Anomaly', 'An unusual day or record that does not match normal behavior.'],
  ['Forecast', 'An estimate of the future based on past patterns.'],
  ['Held-out error', 'How far off the forecast was when tested on recent history it had not seen.'],
  ['Baseline', 'A simple rule used as a yardstick.'],
  ['Segment', 'A group of records that behave alike.'],
  ['Score', 'How unusual a flagged record is; higher means more unusual.'],
  ['Risk level', 'A plain label for how likely the outcome is: Low, Medium or High.'],
  ['Aggregated', 'Added up into groups so no single record can be identified.'],
];

export function UserManual() {
  const contract = useContract();
  const term = useTerm();
  const searchId = useId();
  const [query, setQuery] = useState('');
  const project = contract.data ? contract.data.project : { domain: '' };
  const sections = useMemo(() => buildSections(term, project), [term, project]);
  const q = query.trim().toLowerCase();
  const shown = q ? sections.filter(s => (s.title + ' ' + s.body.join(' ')).toLowerCase().includes(q)) : sections;
  const glossary = q ? GLOSSARY.filter(([t, m]) => (t + ' ' + m).toLowerCase().includes(q)) : GLOSSARY;
  return (
    <div className="stack manual">
      <div className="manual-tools">
        <div className="field">
          <label htmlFor={searchId}>Search the guide</label>
          <input id={searchId} type="search" value={query} onChange={e => setQuery(e.target.value)} />
        </div>
        <button type="button" className="btn-secondary" onClick={() => window.print()}>Print</button>
      </div>
      {shown.length === 0 && glossary.length === 0 ? <div className="card state-box"><p>Nothing in the guide matches that search.</p></div> : null}
      {shown.map(s => (
        <section className="card" key={s.id}>
          <h2><Highlight text={s.title} query={query} /></h2>
          {s.body.map((p, i) => <p key={s.id + '-' + i}><Highlight text={p} query={query} /></p>)}
        </section>
      ))}
      {glossary.length > 0 ? (
        <section className="card">
          <h2>Glossary</h2>
          <GlossaryTable entries={glossary} query={query} />
        </section>
      ) : null}
    </div>
  );
}
"""

FILES["src/components/health/DataHealth.jsx"] = r"""import { useDataset } from '../../hooks/useDataset.js';
import { useContract } from '../../hooks/useContract.js';
import { useFormat } from '../../context/FormatContext.jsx';
import { DataState } from '../shared/DataState.jsx';
import { SkeletonCard } from '../shared/SkeletonCard.jsx';
import { DATASETS } from '../../utils/datasets.js';
import { predictMode } from '../../utils/predict.js';

function DatasetRow({ name }) {
  const q = useDataset(name);
  let state = 'Loaded';
  let cls = 'status status-ok';
  if (q.loading) { state = 'Loading'; cls = 'status status-none'; }
  else if (q.error) {
    state = q.error.kind === 'skipped' ? 'Skipped: ' + q.error.message : q.error.kind === 'missing' || q.error.kind === 'empty' ? 'Missing' : 'Invalid: ' + q.error.message;
    cls = q.error.kind === 'skipped' ? 'status status-warn' : 'status status-bad';
  }
  return <tr><th scope="row">{name}</th><td><span className={cls}>{state}</span></td></tr>;
}

function PredictModeLine() {
  const scorer = useDataset('scorer');
  const lookup = useDataset('forecastLookup');
  const forecast = useDataset('forecast');
  if (scorer.loading || lookup.loading || forecast.loading) return <p className="muted">Checking the Predict page.</p>;
  return <p>{'Predict page mode: ' + predictMode(scorer, lookup, forecast)}</p>;
}

function Overview() {
  const query = useDataset('summary');
  const contract = useContract();
  const fmt = useFormat();
  if (query.loading || query.error) {
    return <DataState query={query} label="summary" skeleton={<SkeletonCard count={2} height={120} />} />;
  }
  const s = query.data;
  return (
    <section className="card">
      <h2>Last run</h2>
      <dl className="detail-list">
        <div className="detail-pair"><dt>Updated</dt><dd>{s.lastRun ? fmt.ago(s.lastRun) + ' (' + fmt.date(s.lastRun) + ')' : '-'}</dd></div>
        <div className="detail-pair"><dt>Data source</dt><dd>{s.source || '-'}</dd></div>
        <div className="detail-pair"><dt>Rows</dt><dd>{fmt.value(s.rows, 'integer')}</dd></div>
        <div className="detail-pair"><dt>Date range</dt><dd>{s.dateRange.start ? fmt.date(s.dateRange.start) + ' to ' + fmt.date(s.dateRange.end) : '-'}</dd></div>
        <div className="detail-pair"><dt>Contract version</dt><dd>{contract.data ? contract.data.schemaVersion : '-'}</dd></div>
      </dl>
    </section>
  );
}

function RunStages() {
  const query = useDataset('runLog');
  if (query.loading || query.error) {
    return <DataState query={query} label="run log" skeleton={<SkeletonCard count={1} height={120} />} />;
  }
  const run = query.data[0];
  if (!run) return <div className="card state-box"><p>No runs are recorded yet.</p></div>;
  return (
    <section className="card table-card">
      <h2>Latest run steps</h2>
      <div className="table-scroll">
        <table className="data-table">
          <thead><tr><th scope="col">Step</th><th scope="col">Status</th><th scope="col">Seconds</th><th scope="col">Reason</th></tr></thead>
          <tbody>
            {run.stages.map((st, i) => (
              <tr key={st.name + '-' + i}><th scope="row">{st.name}</th><td>{st.status}</td><td>{st.seconds === null ? '-' : st.seconds}</td><td>{st.reason || '-'}</td></tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export function DataHealth() {
  return (
    <div className="stack">
      <Overview />
      <RunStages />
      <section className="card table-card">
        <h2>Data files</h2>
        <PredictModeLine />
        <div className="table-scroll">
          <table className="data-table">
            <thead><tr><th scope="col">Dataset</th><th scope="col">State</th></tr></thead>
            <tbody>
              {Object.keys(DATASETS).map(name => <DatasetRow key={name} name={name} />)}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
"""

FILES["src/pages/Dashboard.jsx"] = r"""import { PageSection } from '../components/shared/PageSection.jsx';
import { ErrorBoundary } from '../components/shared/ErrorBoundary.jsx';
import { KPICards } from '../components/understand/KPICards.jsx';
import { ChartGrid } from '../components/understand/ChartGrid.jsx';
import { SegmentExplorer } from '../components/understand/SegmentExplorer.jsx';
import { AnomalyTable } from '../components/understand/AnomalyTable.jsx';
import { InsightCards } from '../components/decide/InsightCards.jsx';
import { RecommendationEngine } from '../components/decide/RecommendationEngine.jsx';
import { WhatIfSimulator } from '../components/decide/WhatIfSimulator.jsx';
import { GoalTracker } from '../components/decide/GoalTracker.jsx';
import { Forecaster } from '../components/monitor/Forecaster.jsx';
import { Predictor } from '../components/monitor/Predictor.jsx';
import { GoalProgress } from '../components/monitor/GoalProgress.jsx';
import { AlertCenter } from '../components/monitor/AlertCenter.jsx';
import { InteractiveExplorer } from '../components/explorer/InteractiveExplorer.jsx';
import { UserManual } from '../components/manual/UserManual.jsx';
import { DataHealth } from '../components/health/DataHealth.jsx';

export const DEFAULT_PAGE = 'understand/overview';

const PAGES = {
  'understand/overview': { title: 'Overview', intro: 'Key numbers and the charts that explain them.', render: () => (<><KPICards /><ChartGrid /></>) },
  'understand/segments': { title: 'Segments', intro: 'Groups of similar records.', render: () => <SegmentExplorer /> },
  'understand/anomalies': { title: 'Anomalies', intro: 'Unusual records worth a second look.', render: () => <AnomalyTable /> },
  'decide/insights': { title: 'Insights', intro: 'What the data says and what to do about it.', render: () => <InsightCards /> },
  'decide/recommendations': { title: 'Recommendations', intro: 'Actions in order of priority.', render: () => <RecommendationEngine /> },
  'decide/what-if': { title: 'What-if', intro: 'See how a change could play out.', render: () => <WhatIfSimulator /> },
  'decide/goals': { title: 'Goals', intro: 'Targets and how you are doing against them.', render: () => <GoalTracker /> },
  'monitor/forecast': { title: 'Forecast', intro: 'An estimate of what comes next.', render: () => <Forecaster /> },
  'monitor/predict': { title: 'Predict', intro: 'Enter details and get an estimate before it happens.', render: () => <Predictor /> },
  'monitor/progress': { title: 'Progress', intro: 'Latest values against targets.', render: () => <GoalProgress /> },
  'monitor/alerts': { title: 'Alerts', intro: 'Things that need attention now.', render: () => <AlertCenter /> },
  explore: { title: 'Explore', intro: 'Slice the numbers your own way.', render: () => <InteractiveExplorer /> },
  guide: { title: 'Guide', intro: 'A plain-English manual for this dashboard.', render: () => <UserManual /> },
  health: { title: 'Data health', intro: 'When the data was last updated and what is available.', render: () => <DataHealth /> },
};

export const PAGE_IDS = Object.keys(PAGES);

export function Dashboard({ route }) {
  const page = PAGES[route] || PAGES[DEFAULT_PAGE];
  return (
    <PageSection title={page.title} intro={page.intro}>
      <ErrorBoundary key={route} label={page.title}>
        {page.render()}
      </ErrorBoundary>
    </PageSection>
  );
}
"""

FILES["src/App.jsx"] = r"""import { TerminologyProvider } from './context/TerminologyContext.jsx';
import { FormatProvider } from './context/FormatContext.jsx';
import { ExplorerProvider } from './context/ExplorerContext.jsx';
import { useContract } from './hooks/useContract.js';
import { useHashRoute } from './hooks/useHashRoute.js';
import { Sidebar } from './components/shared/Sidebar.jsx';
import { Header } from './components/shared/Header.jsx';
import { ErrorBoundary } from './components/shared/ErrorBoundary.jsx';
import { Dashboard, PAGE_IDS, DEFAULT_PAGE } from './pages/Dashboard.jsx';

function Shell() {
  const [route] = useHashRoute(PAGE_IDS, DEFAULT_PAGE);
  const contract = useContract();
  return (
    <div className="app-shell">
      <Sidebar route={route} />
      <div className="main">
        <Header />
        {contract.error ? (
          <p className="banner" role="status">The data contract could not be read, so some sections may fall back to default file locations.</p>
        ) : null}
        <main className="content" id="content">
          <ErrorBoundary label="This page">
            <Dashboard route={route} />
          </ErrorBoundary>
        </main>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <TerminologyProvider>
      <FormatProvider>
        <ExplorerProvider>
          <Shell />
        </ExplorerProvider>
      </FormatProvider>
    </TerminologyProvider>
  );
}
"""

FILES["src/main.jsx"] = r"""import { createRoot } from 'react-dom/client';
import App from './App.jsx';
import './styles/tokens.css';
import './styles/base.css';
import './styles/components.css';

createRoot(document.getElementById('root')).render(<App />);
"""

FILES["src/styles/tokens.css"] = r"""/* Every color, size and spacing value used by the app is defined here once. */
:root {
  --color-bg: #f8fafc;
  --color-surface: #ffffff;
  --color-surface-2: #f1f5f9;
  --color-border: #e2e8f0;
  --color-text-primary: #0f172a;
  --color-text-secondary: #475569;
  --color-accent: __ACCENT__;
  --color-accent-soft: color-mix(in srgb, var(--color-accent) 14%, transparent);
  --color-on-accent: __ON_ACCENT__;
  --color-danger: #b91c1c;
  --color-warning: #b45309;
  --color-success: #15803d;
  --color-sidebar-bg: __SIDEBAR__;
  --color-sidebar-text: #e2e8f0;
  --chart-1: #2563eb;
  --chart-2: #f59e0b;
  --chart-3: #10b981;
  --chart-4: #8b5cf6;
  --chart-5: #ef4444;
  --chart-6: #06b6d4;
  --shadow-card: 0 1px 2px rgba(15, 23, 42, 0.06), 0 1px 3px rgba(15, 23, 42, 0.08);
  --shadow-card-hover: 0 2px 4px rgba(15, 23, 42, 0.08), 0 4px 10px rgba(15, 23, 42, 0.1);
  --radius-card: 0.75rem;
  --radius-pill: 1.25rem;
  --space-1: 0.25rem;
  --space-2: 0.5rem;
  --space-3: 0.75rem;
  --space-4: 1rem;
  --space-5: 1.25rem;
  --space-6: 1.5rem;
  --space-8: 2rem;
  --space-10: 2.5rem;
  --space-12: 3rem;
  --font-heading: '__FONT_HEADING__', system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  --font-body: '__FONT_BODY__', system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  --font-size-xs: 0.75rem;
  --font-size-sm: 0.875rem;
  --font-size-md: 1rem;
  --font-size-lg: 1.125rem;
  --font-size-xl: 1.5rem;
  --font-size-2xl: 1.875rem;
  --transition-fast: 150ms ease;
}

[data-theme="dark"] {
  --color-bg: #0f172a;
  --color-surface: #1e293b;
  --color-surface-2: #334155;
  --color-border: #334155;
  --color-text-primary: #f1f5f9;
  --color-text-secondary: #94a3b8;
  --color-accent: __ACCENT_DARK__;
  --color-on-accent: __ON_ACCENT_DARK__;
  --color-danger: #f87171;
  --color-warning: #fbbf24;
  --color-success: #34d399;
  --chart-1: #60a5fa;
  --chart-2: #fbbf24;
  --chart-3: #34d399;
  --chart-4: #a78bfa;
  --chart-5: #f87171;
  --chart-6: #22d3ee;
  --shadow-card: 0 1px 2px rgba(0, 0, 0, 0.4);
  --shadow-card-hover: 0 2px 8px rgba(0, 0, 0, 0.5);
}
"""

FILES["src/styles/base.css"] = r"""*, *::before, *::after { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }
body {
  margin: 0;
  background: var(--color-bg);
  color: var(--color-text-primary);
  font-family: var(--font-body);
  font-size: var(--font-size-md);
  line-height: 1.5;
}
h1, h2, h3 { font-family: var(--font-heading); line-height: 1.25; margin: 0 0 var(--space-2); }
h1 { font-size: var(--font-size-2xl); }
h2 { font-size: var(--font-size-xl); }
h3 { font-size: var(--font-size-lg); }
p { margin: 0 0 var(--space-2); }
ul { margin: 0; padding: 0; list-style: none; }
a { color: var(--color-text-primary); text-underline-offset: 0.2em; }
button, input, select { font: inherit; color: inherit; }
:focus-visible { outline: 0.1875rem solid var(--color-accent); outline-offset: 0.125rem; }

.app-shell { display: grid; grid-template-columns: 15rem minmax(0, 1fr); min-height: 100vh; }
.sidebar {
  background: var(--color-sidebar-bg);
  color: var(--color-sidebar-text);
  position: sticky;
  top: 0;
  height: 100vh;
  overflow-y: auto;
  padding: var(--space-5) var(--space-3);
}
.sidebar-brand { font-family: var(--font-heading); font-size: var(--font-size-lg); font-weight: 700; padding: 0 var(--space-3) var(--space-4); }
.sidebar-group { margin-bottom: var(--space-4); }
.sidebar-title { font-size: var(--font-size-xs); text-transform: uppercase; letter-spacing: 0.08em; opacity: 0.7; padding: 0 var(--space-3); margin-bottom: var(--space-1); }
.sidebar-link {
  display: flex; align-items: center; gap: var(--space-3);
  color: inherit; text-decoration: none;
  padding: var(--space-2) var(--space-3);
  border-left: 0.1875rem solid transparent;
  border-radius: 0 0.5rem 0.5rem 0;
  font-size: var(--font-size-sm);
  transition: background var(--transition-fast);
}
.sidebar-link:hover { background: color-mix(in srgb, var(--color-sidebar-text) 10%, transparent); }
.sidebar-link.active { border-left-color: var(--color-accent); background: var(--color-accent-soft); font-weight: 600; }
.main { min-width: 0; display: flex; flex-direction: column; }
.topbar {
  position: sticky; top: 0; z-index: 5;
  display: flex; align-items: center; justify-content: space-between;
  padding: var(--space-3) var(--space-6);
  background: var(--color-surface);
  border-bottom: 1px solid var(--color-border);
}
.topbar-name { font-family: var(--font-heading); font-weight: 600; margin: 0; }
.content { width: 100%; max-width: 80rem; padding: var(--space-6); margin: 0 auto; }
.banner { background: var(--color-accent-soft); padding: var(--space-3) var(--space-6); margin: 0; font-size: var(--font-size-sm); }

@media (max-width: 900px) {
  .app-shell { grid-template-columns: minmax(0, 1fr); }
  .sidebar { position: static; height: auto; display: flex; flex-wrap: nowrap; gap: var(--space-4); overflow-x: auto; overflow-y: hidden; padding: var(--space-3); align-items: center; }
  .sidebar-brand { padding: 0; white-space: nowrap; }
  .sidebar-group { margin: 0; display: flex; align-items: center; gap: var(--space-2); }
  .sidebar-group ul { display: flex; gap: var(--space-1); }
  .sidebar-title { display: none; }
  .sidebar-link { white-space: nowrap; border-left: 0; border-bottom: 0.1875rem solid transparent; border-radius: 0.5rem; }
  .sidebar-link.active { border-bottom-color: var(--color-accent); }
  .content { padding: var(--space-4); }
}

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation: none !important; transition: none !important; }
}
"""

FILES["src/styles/components.css"] = r""".icon { width: 1.25rem; height: 1.25rem; flex: none; }
.muted { color: var(--color-text-secondary); }
.small { font-size: var(--font-size-sm); }
.sr-only { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
.stack { display: flex; flex-direction: column; gap: var(--space-5); min-width: 0; }
.page-head { margin-bottom: var(--space-5); }
.grid { display: grid; gap: var(--space-4); grid-template-columns: repeat(auto-fit, minmax(16rem, 1fr)); }
.grid.wide { grid-template-columns: repeat(auto-fit, minmax(20rem, 1fr)); }
.chart-grid { grid-template-columns: repeat(auto-fit, minmax(min(100%, 24rem), 1fr)); margin-top: var(--space-4); }
.kpi-grid { margin-bottom: var(--space-2); }

.card {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-card);
  padding: var(--space-5);
  min-width: 0;
  transition: box-shadow var(--transition-fast), transform var(--transition-fast);
}
.card:hover { box-shadow: var(--shadow-card-hover); transform: translateY(-1px); }
.card-head { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); margin-bottom: var(--space-2); }
.state-box { text-align: left; }
.table-card { padding: var(--space-4); }
.group-title { margin-top: var(--space-2); }

.kpi-label { color: var(--color-text-secondary); font-size: var(--font-size-sm); margin: 0; }
.kpi-value { font-family: var(--font-heading); font-size: var(--font-size-2xl); font-weight: 700; margin: var(--space-1) 0; }
.kpi-trend { display: flex; align-items: center; gap: var(--space-1); font-size: var(--font-size-sm); color: var(--color-text-secondary); }

.chart-box { height: 22rem; min-width: 0; }
.chart-scroll { overflow: auto; }
.chart-card h3 { margin-bottom: var(--space-1); }
.heat-wrap { min-width: 0; }
.heat { display: grid; gap: var(--space-1); align-items: center; }
.heat-row { display: contents; }
.heat-head { font-size: var(--font-size-xs); color: var(--color-text-secondary); padding-right: var(--space-2); }
.heat-cell { height: 1.75rem; border-radius: 0.25rem; border: 1px solid var(--color-border); }

.badge { display: inline-block; font-size: var(--font-size-xs); font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; }
.badge-high { color: var(--color-danger); }
.badge-medium { color: var(--color-warning); }
.badge-low { color: var(--color-success); }
.status { font-size: var(--font-size-sm); font-weight: 600; }
.status-ok { color: var(--color-success); }
.status-warn { color: var(--color-warning); }
.status-bad { color: var(--color-danger); }
.status-none { color: var(--color-text-secondary); }

.chips { display: flex; flex-wrap: wrap; gap: var(--space-2); }
.chip { background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-pill); padding: var(--space-1) var(--space-4); cursor: pointer; font-size: var(--font-size-sm); }
.chip.active { background: var(--color-accent); border-color: var(--color-accent); color: var(--color-on-accent); }
.callout { background: var(--color-accent-soft); border-radius: 0.5rem; padding: var(--space-3); margin-top: var(--space-3); }
.callout-title { font-weight: 700; font-size: var(--font-size-sm); margin-bottom: var(--space-1); }

.btn-primary, .btn-secondary, .icon-btn, .th-btn { cursor: pointer; border-radius: 0.5rem; transition: background var(--transition-fast); }
.btn-primary { background: var(--color-accent); color: var(--color-on-accent); border: 1px solid var(--color-accent); padding: var(--space-2) var(--space-5); font-weight: 600; }
.btn-secondary { background: var(--color-surface); border: 1px solid var(--color-border); padding: var(--space-2) var(--space-4); }
.btn-secondary:hover:not(:disabled) { background: var(--color-surface-2); }
.btn-primary:disabled, .btn-secondary:disabled { opacity: 0.5; cursor: not-allowed; }
.icon-btn { background: transparent; border: 1px solid var(--color-border); padding: var(--space-2); display: inline-flex; }
.th-btn { background: transparent; border: 0; padding: 0; font-weight: 700; text-align: left; }

.field { display: flex; flex-direction: column; gap: var(--space-1); min-width: 0; }
.field label, .filter span { font-size: var(--font-size-sm); font-weight: 600; }
input[type="number"], input[type="search"], input[type="text"], select {
  background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 0.5rem; padding: var(--space-2) var(--space-3); min-width: 0; max-width: 100%;
}
input[type="range"] { width: 100%; accent-color: var(--color-accent); }
.field-grid { display: grid; gap: var(--space-4); grid-template-columns: repeat(auto-fit, minmax(14rem, 1fr)); margin-bottom: var(--space-4); }
.field-help { color: var(--color-text-secondary); font-size: var(--font-size-xs); margin: 0; }
.field-warning { color: var(--color-warning); font-size: var(--font-size-sm); margin: 0; }
.field-error { color: var(--color-danger); font-size: var(--font-size-sm); }
.form-actions { display: flex; gap: var(--space-3); flex-wrap: wrap; }
.predictor-result { margin-top: var(--space-5); padding-top: var(--space-4); border-top: 1px solid var(--color-border); }
.result-value { font-family: var(--font-heading); font-size: var(--font-size-2xl); font-weight: 700; margin: 0; }
.result-label { font-weight: 600; }
.driver-list { list-style: disc; padding-left: var(--space-5); margin-bottom: var(--space-3); }
.plain-list { list-style: disc; padding-left: var(--space-5); }

.table-scroll { overflow-x: auto; }
.data-table { width: 100%; border-collapse: collapse; font-size: var(--font-size-sm); }
.data-table th, .data-table td { text-align: left; padding: var(--space-2) var(--space-3); border-bottom: 1px solid var(--color-border); vertical-align: top; }
.data-table thead th { background: var(--color-surface-2); }
.pager { display: flex; align-items: center; justify-content: space-between; margin-top: var(--space-3); gap: var(--space-3); }

.bar-track { display: block; height: 0.5rem; background: var(--color-surface-2); border-radius: var(--radius-pill); overflow: hidden; margin: var(--space-2) 0; }
.bar-fill { display: block; height: 100%; background: var(--color-accent); }
.segment-card { text-align: left; cursor: pointer; display: flex; flex-direction: column; gap: var(--space-1); font: inherit; color: inherit; }
.segment-name { font-weight: 600; }

.filter-bar { position: sticky; top: 3.75rem; z-index: 4; display: flex; flex-wrap: wrap; gap: var(--space-3); align-items: flex-end; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-card); padding: var(--space-3) var(--space-4); }
.filter { display: flex; flex-direction: column; gap: var(--space-1); }
.filter-actions { display: flex; gap: var(--space-2); align-items: center; flex-wrap: wrap; }

.detail-list { margin: 0; }
.detail-pair { display: flex; justify-content: space-between; gap: var(--space-4); padding: var(--space-2) 0; border-bottom: 1px solid var(--color-border); }
.detail-list dt { color: var(--color-text-secondary); }
.detail-list dd { margin: 0; font-weight: 600; }
.drill-backdrop { position: fixed; inset: 0; background: color-mix(in srgb, var(--color-text-primary) 45%, transparent); z-index: 20; display: flex; justify-content: flex-end; }
.drill-panel { width: min(100%, 26rem); height: 100%; overflow-y: auto; background: var(--color-surface); padding: var(--space-5); box-shadow: var(--shadow-card-hover); }
.drill-head { display: flex; justify-content: space-between; align-items: center; gap: var(--space-3); }
.drill-body { margin: var(--space-4) 0; }

.skeleton { background: linear-gradient(90deg, var(--color-surface-2), var(--color-surface), var(--color-surface-2)); background-size: 200% 100%; animation: shimmer 1.4s linear infinite; }
@keyframes shimmer { from { background-position: 200% 0; } to { background-position: -200% 0; } }

.manual-tools { display: flex; gap: var(--space-4); align-items: flex-end; flex-wrap: wrap; }
.manual-tools .field { flex: 1 1 16rem; }
mark { background: var(--color-accent-soft); color: inherit; border-radius: 0.125rem; }

@media print {
  .sidebar, .topbar, .manual-tools, .banner { display: none !important; }
  .app-shell { display: block; }
  .content { max-width: none; padding: 0; }
  .card { box-shadow: none; break-inside: avoid; }
  @page { size: A4; margin: 15mm; }
}
"""
TOOLING = {}

TOOLING["audit_frontend.py"] = r"""import getpass
import hashlib
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
TEXT_EXT = {'.js', '.jsx', '.mjs', '.css', '.html', '.json', '.toml', '.md', '.svg', '.example'}
VOCAB = [r'claude', r'anthropic', r'chatgpt', r'openai', r'\bllm\b', r'as an ai', r'\bskill\b']
SKIP = {'node_modules', 'dist', '.wrangler'}


def locate():
    for proj in (BASE / BASE.name, BASE):
        if (proj / 'frontend' / 'package.json').is_file():
            return proj
    for child in sorted(BASE.iterdir()):
        if child.is_dir() and (child / 'frontend' / 'package.json').is_file():
            return child
    return None


def walk(root):
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if d not in SKIP]
        for f in fn:
            yield Path(dp) / f


def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    blockers, warnings, infos = [], [], []
    proj = locate()
    if proj is None:
        print('No frontend folder found next to this script.')
        return 2
    fe = proj / 'frontend'
    be = proj / 'backend'
    data_dir = fe / 'public' / 'data'
    user = ''
    try:
        user = getpass.getuser()
    except Exception:
        pass
    count = 0
    for path in walk(fe):
        rel = path.relative_to(fe).as_posix()
        if path.suffix.lower() not in TEXT_EXT and path.name not in ('_headers', '.gitignore'):
            continue
        try:
            text = path.read_text(encoding='utf-8')
        except Exception:
            warnings.append(rel + ': could not be read as text')
            continue
        count += 1
        in_data = rel.startswith('public/data/')
        in_src = rel.startswith('src/')
        if re.search(r'[A-Za-z]:\\{1,2}(Users|Windows)|/Users/|/home/', text):
            blockers.append(rel + ': contains an absolute local path')
        if len(user) >= 4 and user.lower() not in ('user', 'admin', 'root', 'owner') and user.lower() in text.lower():
            blockers.append(rel + ': contains the OS user name')
        if in_data:
            continue
        for pat in VOCAB:
            if re.search(pat, text, re.I):
                blockers.append(rel + ': vocabulary check matched ' + pat)
        if '\u2014' in text:
            blockers.append(rel + ': contains an em dash')
        if rel != 'scripts/refresh-data.mjs':
            for needle in ('backend/', '_tooling', '_casefile', str(BASE)):
                if needle and needle in text:
                    blockers.append(rel + ': mentions ' + needle)
        if re.search(r'(api[_-]?key|secret|password)\s*[:=]\s*[\'"][A-Za-z0-9_\-]{16,}', text, re.I):
            blockers.append(rel + ': looks like it contains a secret')
        if in_src and path.suffix in ('.js', '.jsx', '.css'):
            if not rel.endswith('tokens.css') and re.search(r'#[0-9a-fA-F]{3,8}\b', text):
                blockers.append(rel + ': hex color outside tokens.css')
            for pat in (r'dangerouslySetInnerHTML', r'innerHTML', r'\beval\(', r'document\.write', r'console\.log\('):
                if re.search(pat, text):
                    blockers.append(rel + ': forbidden API ' + pat)
            if 'fetch(' in text and not rel.endswith('hooks/useData.js'):
                blockers.append(rel + ': fetch( outside useData.js')
    infos.append('Files scanned: ' + str(count))

    wrangler = fe / 'wrangler.toml'
    if wrangler.is_file():
        w = wrangler.read_text(encoding='utf-8')
        name = re.search(r'^name\s*=\s*"([^"]*)"', w, re.M)
        compat = re.search(r'^compatibility_date\s*=\s*"([^"]*)"', w, re.M)
        mode = re.search(r'^MCP_MODE\s*=\s*"([^"]*)"', w, re.M)
        if not name or not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,53}', name.group(1)):
            blockers.append('wrangler.toml: worker name is not valid')
        if not compat or compat.group(1) > date.today().isoformat():
            blockers.append('wrangler.toml: compatibility date is missing or in the future')
        if not mode or mode.group(1) not in ('off', 'token', 'open'):
            blockers.append('wrangler.toml: MCP_MODE must be off, token or open')
        elif mode.group(1) != 'off':
            warnings.append('MCP_MODE is ' + mode.group(1) + ': the /mcp route is reachable')
    else:
        blockers.append('wrangler.toml is missing')
    pkg = fe / 'package.json'
    try:
        p = json.loads(pkg.read_text(encoding='utf-8'))
        if p.get('type') != 'module' or 'main' in p or '>=22' not in str(p.get('engines', {}).get('node', '')):
            blockers.append('package.json: type, main or engines are wrong')
        for dep in ('react-router-dom',):
            if dep in p.get('dependencies', {}):
                blockers.append('package.json: unexpected dependency ' + dep)
    except Exception as exc:
        blockers.append('package.json cannot be read: ' + str(exc))
    if not (fe / 'public' / '_headers').is_file():
        blockers.append('public/_headers is missing')

    out = be / 'output'
    if out.is_dir() and data_dir.is_dir():
        a = {p.relative_to(out).as_posix(): sha(p) for p in out.rglob('*') if p.is_file()}
        b = {p.relative_to(data_dir).as_posix(): sha(p) for p in data_dir.rglob('*') if p.is_file()}
        if a != b:
            warnings.append('public/data differs from backend/output (stale data); run npm run check in the frontend folder')
        else:
            infos.append('public/data matches backend/output')
    elif not data_dir.is_dir():
        blockers.append('public/data is missing')
    fp_file = HERE / 'backend_fingerprint.json'
    if fp_file.is_file() and be.is_dir():
        saved = json.loads(fp_file.read_text(encoding='utf-8'))
        now = {p.relative_to(be).as_posix(): sha(p) for p in be.rglob('*') if p.is_file()}
        changed = sorted(k for k in set(saved) | set(now) if saved.get(k) != now.get(k))
        if changed:
            blockers.append('backend files changed since the build: ' + ', '.join(changed[:10]))
        else:
            infos.append('Backend fingerprint unchanged')
    allowed = {'backend', 'frontend', 'README.md', '.gitignore'}
    extra = sorted(e.name for e in proj.iterdir() if e.name not in allowed)
    if extra:
        warnings.append('Project folder holds other entries: ' + ', '.join(extra))

    report = ['FRONTEND AUDIT', '']
    for title, rows in (('BLOCKER', blockers), ('WARNING', warnings), ('INFO', infos)):
        report.append(title + ' (' + str(len(rows)) + ')')
        report.extend('  ' + r for r in rows)
        report.append('')
    case = BASE / '_casefile'
    case.mkdir(exist_ok=True)
    (case / 'frontend_audit_report.txt').write_text('\n'.join(report), encoding='utf-8')
    print('\n'.join(report))
    return 1 if blockers else 0


if __name__ == '__main__':
    sys.exit(main())
"""

TOOLING["finish_frontend.py"] = r"""import subprocess
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
BEGIN = '==== FRONTEND SECTION BEGIN ===='
END = '==== FRONTEND SECTION END ===='

QA = [
    ('Why a static-assets Worker?', 'The site is static files plus two small routes. Static assets are served by the platform, and the Worker only owns /api and /mcp.'),
    ('Why a data contract?', 'One JSON file lists every dataset and where it lives, so the pages never guess paths and a missing file is reported by name.'),
    ('Why adapters?', 'Adapters turn each file into one shape for the pages and accept older shapes, so a small change upstream does not blank a panel.'),
    ('How are charts kept correct in dark mode?', 'Chart colors are read from the computed theme tokens and refreshed when the theme attribute changes, so SVG never depends on var() resolution.'),
    ('What happens when a stage is skipped?', 'The file carries a skipped status and a reason. The page shows that reason instead of numbers; nothing is invented.'),
    ('How is data refreshed?', 'npm run check, dev and build copy the backend output into public/data and validate it. npm run deploy does the same before publishing.'),
    ('What stops the frontend from overwriting the backend?', 'Writes are limited to the frontend, tooling and case folders by a path check, and a backend fingerprint is compared before and after.'),
    ('How is access controlled?', 'The app has no login. Put the address behind an access policy; data files are public to anyone who can open the site.'),
    ('What are the three MCP modes?', 'off (default, 404), token (bearer token set as a secret) and open (no token, for synthetic data only).'),
    ('Why is Predict computed in the browser?', 'Scoring parameters are static files, so there is no secret, no size limit and no server call; inputs never leave the page.'),
    ('How accurate is the Predict page?', 'Linear scoring reproduces the exported model. Neighbour scoring approximates it; the measured fidelity is shown in the scoring file.'),
    ('What if there is no scoring file?', 'The Predict page still exists. It explains why and shows the input fields disabled.'),
    ('How does the explorer protect privacy?', 'It works on a pre-aggregated cube, so no row-level records are in the browser.'),
    ('Where are goals stored?', 'Targets entered in the browser are kept in local storage on that device only.'),
    ('What does the data check do?', 'It runs every adapter over every file, reports OK, UNAVAILABLE, MISSING or INVALID, runs a test prediction and rejects local file paths.'),
    ('How is the what-if tool computed?', 'It reads along a pre-computed table with straight-line interpolation; it does not run a model.'),
    ('Why Recharts?', 'It is a maintained React chart library that renders to SVG and works with the theme tokens.'),
]

PROCESS = ('Process note: the frontend was produced by a generator script written with an AI assistant and checked with '
           'automated lint, a data check and an audit script. Questions about the process are answered truthfully.')


def main():
    audit = subprocess.run([sys.executable, str(HERE / 'audit_frontend.py')])
    case = BASE / '_casefile'
    case.mkdir(exist_ok=True)
    notes = case / 'case_notes.txt'
    lines = [BEGIN, 'Written ' + datetime.now().isoformat(timespec='seconds'), '',
             'ARCHITECTURE',
             '  React 18 + Vite, Recharts, hash router, no extra runtime dependencies.',
             '  src/utils holds pure logic (adapters, cube, predict, formatters); src/hooks the data layer; src/components the pages.',
             '  worker/index.js serves /api/forecast and a read-only /mcp; everything else is static.', '',
             'STATE HANDLING',
             '  Every data component shows a skeleton, then data or a specific message for skipped, missing, invalid or network states.', '',
             'KNOWN LIMITS',
             '  Data files are public without an access policy; goals entered in the browser are device-only; lookup is nearest-entry.', '',
             'QUESTIONS AND ANSWERS']
    for i, (q, a) in enumerate(QA, 1):
        lines.append(str(i) + '. ' + q)
        lines.append('   ' + a)
    lines += ['', PROCESS, END, '']
    section = '\n'.join(lines)
    if notes.is_file():
        text = notes.read_text(encoding='utf-8')
        if BEGIN in text and END in text:
            head = text.split(BEGIN)[0]
            tail = text.split(END, 1)[1]
            text = head + section + tail.lstrip('\n')
        else:
            text = text.rstrip('\n') + '\n\n' + section
    else:
        text = 'CASE NOTES\n\n' + section
    notes.write_text(text, encoding='utf-8')
    print('Case notes updated: ' + str(notes))
    print('Read _casefile/frontend_audit_report.txt, then delete generate_react_frontend.py and _tooling.')
    return audit.returncode


if __name__ == '__main__':
    sys.exit(main())
"""
# ---------------------------------------------------------------- lint
EMOJI_RE = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\uFE0F]")
HOOKS = ["useState", "useEffect", "useMemo", "useRef", "useCallback", "useContext", "useId"]
RECHARTS = ["ResponsiveContainer", "BarChart", "Bar", "LineChart", "Line", "ScatterChart", "Scatter", "XAxis", "YAxis",
            "CartesianGrid", "Tooltip", "PieChart", "Pie", "Cell", "Legend", "ComposedChart", "Area"]


def check_balance(src):
    stack, i, n, prev = [], 0, len(src), ""
    pairs = {")": "(", "]": "[", "}": "{"}

    def scan_template(j):
        while j < n:
            ch = src[j]
            if ch == "\\":
                j += 2
                continue
            if ch == "`":
                return j + 1, False
            if ch == "$" and src[j + 1:j + 2] == "{":
                stack.append("T")
                return j + 2, True
            j += 1
        return n, False

    while i < n:
        c = src[i]
        if c in " \t\r\n":
            i += 1
            continue
        if c == "/" and src[i + 1:i + 2] == "/":
            j = src.find("\n", i)
            i = n if j < 0 else j
            continue
        if c == "/" and src[i + 1:i + 2] == "*":
            j = src.find("*/", i + 2)
            if j < 0:
                return "unterminated comment"
            i = j + 2
            continue
        if c in "'\"":
            j = i + 1
            while j < n and src[j] != c:
                if src[j] == "\\":
                    j += 1
                elif src[j] == "\n":
                    return "unterminated string near: " + src[i:i + 40].replace("\n", " ")
                j += 1
            if j >= n:
                return "unterminated string"
            i, prev = j + 1, '"'
            continue
        if c == "`":
            i, _ = scan_template(i + 1)
            prev = "`"
            continue
        if c == "/" and (prev == "" or prev in "(,=:[!&|?{;"):
            j, in_class = i + 1, False
            while j < n:
                ch = src[j]
                if ch == "\\":
                    j += 2
                    continue
                if ch == "\n":
                    return "unterminated regex near: " + src[i:i + 40]
                if ch == "[":
                    in_class = True
                elif ch == "]":
                    in_class = False
                elif ch == "/" and not in_class:
                    break
                j += 1
            i, prev = j + 1, "/"
            continue
        if c in "([{":
            stack.append(c)
        elif c in ")]}":
            if c == "}" and stack and stack[-1] == "T":
                stack.pop()
                i, _ = scan_template(i + 1)
                prev = "`"
                continue
            if not stack or stack.pop() != pairs[c]:
                return "unbalanced " + c + " near: " + src[max(0, i - 40):i + 10].replace("\n", " ")
        prev = c
        i += 1
    if stack:
        return "unclosed " + "".join(stack)
    return None


def exports_of(src):
    names = set(re.findall(r"export\s+(?:async\s+)?(?:function|const|let|class)\s+([A-Za-z_$][\w$]*)", src))
    for block in re.findall(r"export\s*\{([^}]*)\}", src):
        for part in block.split(","):
            part = part.strip()
            if part:
                names.add(part.split(" as ")[-1].strip())
    if re.search(r"export\s+default", src):
        names.add("default")
    return names


def resolve_import(file, spec, files):
    import posixpath
    base = posixpath.normpath(posixpath.join(posixpath.dirname(file), spec))
    for cand in (base, base + ".js", base + ".jsx", base + "/index.js"):
        if cand in files:
            return cand
    return None


def lint_frontend(files):
    errors, warns = [], []
    code = {k: v for k, v in files.items() if k.endswith((".js", ".jsx", ".mjs"))}
    exp = {k: exports_of(v) for k, v in code.items()}
    for rel, text in files.items():
        in_src = rel.startswith("src/")
        if "\u2014" in text:
            errors.append(rel + ": contains an em dash")
        if EMOJI_RE.search(text):
            errors.append(rel + ": contains an emoji")
        for pat in VOCAB_BLACKLIST:
            if re.search(pat, text, re.I):
                errors.append(rel + ": vocabulary check matched " + pat)
        if re.search(r"__[A-Z][A-Z_]+__", text):
            errors.append(rel + ": unreplaced token")
        if '"""' in text:
            errors.append(rel + ": contains a triple double quote")
        if in_src and re.search(r"deploy|wrangler|cloudflare", text, re.I):
            errors.append(rel + ": mentions deploy, wrangler or cloudflare inside src")
        if in_src and rel.endswith((".js", ".jsx", ".css")) and not rel.endswith("tokens.css"):
            if re.search(r"#[0-9a-fA-F]{3,8}\b", text):
                errors.append(rel + ": hex color outside tokens.css")
            if re.search(r"\brgba?\(", text):
                errors.append(rel + ": rgb color outside tokens.css")
    for rel, text in code.items():
        err = check_balance(text)
        if err:
            errors.append(rel + ": " + err)
        in_src = rel.startswith("src/")
        for m in IMPORT_RE.finditer(text):
            clause, spec = m.group(1).strip(), m.group(2)
            if not spec.startswith("."):
                continue
            target = resolve_import(rel, spec, files)
            if target is None:
                errors.append(rel + ": import does not resolve: " + spec)
                continue
            if not target.endswith((".js", ".jsx")):
                continue
            named = re.search(r"\{([^}]*)\}", clause)
            if named:
                for part in named.group(1).split(","):
                    nm = part.strip().split(" as ")[0].strip()
                    if nm and nm not in exp[target]:
                        errors.append(rel + ": " + nm + " is not exported by " + target)
            head = clause.split("{")[0].strip().rstrip(",").strip()
            if head and not head.startswith("*") and "default" not in exp[target]:
                errors.append(rel + ": " + target + " has no default export")
        for m in SIDE_RE.finditer(text):
            spec = m.group(1)
            if spec.startswith(".") and resolve_import(rel, spec, files) is None:
                errors.append(rel + ": import does not resolve: " + spec)
        if not in_src:
            continue
        if rel.startswith("src/utils/"):
            if re.search(r"from\s+['\"]react", text):
                errors.append(rel + ": utils must not import React")
        for m in re.finditer(r"from\s+['\"](\.[^'\"]*)['\"]", text):
            if rel.startswith("src/utils/") and not m.group(1).endswith(".js"):
                errors.append(rel + ": utils imports need an explicit .js extension")
        if rel.endswith(".jsx"):
            for tag in set(re.findall(r"<([A-Z][A-Za-z0-9]*)\b", text)):
                uses = len(re.findall(r"(?<![<\w/])" + tag + r"\b", text))
                if uses == 0:
                    errors.append(rel + ": <" + tag + "> is not imported or defined")
            for name in RECHARTS:
                if re.search(r"<" + name + r"[\s/>]", text) and not re.search(r"import\s*\{[^}]*\b" + name + r"\b[^}]*\}\s*from\s*'recharts'", text, re.S):
                    errors.append(rel + ": " + name + " is used but not imported from recharts")
        for h in HOOKS:
            if re.search(r"\b" + h + r"\(", text) and not re.search(r"import\s*\{[^}]*\b" + h + r"\b[^}]*\}\s*from\s*'react'", text, re.S):
                errors.append(rel + ": " + h + " is used but not imported from react")
        for ln, line in enumerate(text.split("\n"), 1):
            if line.lstrip().startswith("import ") or " from '" in line:
                continue
            for m in re.finditer(r"\buse[A-Z]\w*\b(?!\s*\()", line):
                errors.append(rel + ":" + str(ln) + ": hook referenced without a call: " + m.group(0))
        for pat in (r"dangerouslySetInnerHTML", r"innerHTML", r"\beval\(", r"document\.write", r"\bclass=", r"console\.log\("):
            if re.search(pat, text):
                errors.append(rel + ": forbidden pattern " + pat)
        if "fetch(" in text and not rel.endswith("hooks/useData.js"):
            errors.append(rel + ": fetch( outside useData.js")
        for m in re.finditer(r"localStorage", text):
            if "try" not in text[max(0, m.start() - 300):m.start()]:
                errors.append(rel + ": localStorage outside a try block")
        if "/data/" in text and not rel.endswith("utils/datasets.js"):
            warns.append(rel + ": contains a /data/ literal")
    pred = files.get("src/components/monitor/Predictor.jsx", "")
    if not re.search(r'type="submit"[^>]*>\s*Predict\s*<', pred):
        errors.append("Predictor.jsx: no submit button labeled Predict")
    if "monitor/predict" not in files.get("src/pages/Dashboard.jsx", ""):
        errors.append("Dashboard.jsx does not route monitor/predict")
    if "monitor/predict" not in files.get("src/components/shared/Sidebar.jsx", ""):
        errors.append("Sidebar.jsx does not link to monitor/predict")
    return errors, warns


IMPORT_RE = re.compile(r"import\s+([^;'\"]*?)\s+from\s+['\"]([^'\"]+)['\"]", re.S)
SIDE_RE = re.compile(r"^import\s+['\"]([^'\"]+)['\"]", re.M)


# ---------------------------------------------------------------- file writing
class Writer:
    def __init__(self, base, roots):
        self.base = base
        self.roots = [r.resolve() for r in roots]
        self.state_path = base / "_tooling" / "frontend_state.json"
        self.state = {}
        if self.state_path.is_file():
            loaded = read_json(self.state_path)
            if isinstance(loaded, dict) and "__read_error__" not in loaded:
                self.state = loaded

    def contained(self, path):
        rp = Path(path).resolve()
        return any(rp == r or r in rp.parents for r in self.roots)

    def key(self, path):
        return Path(path).resolve().relative_to(self.base.resolve()).as_posix()

    def plan(self, items):
        rows = []
        for path, text in items:
            if not self.contained(path):
                die("Refusing to write outside the allowed folders: " + str(path))
            data = text.replace("\r\n", "\n").encode("utf-8")
            digest = hashlib.sha256(data).hexdigest()
            if not path.exists():
                action, target = "create", path
            else:
                current = hashlib.sha256(path.read_bytes()).hexdigest()
                if current == digest:
                    action, target = "unchanged", path
                elif self.state.get(self.key(path)) == current:
                    action, target = "replace", path
                else:
                    target = path.with_name(path.stem + ".new" + path.suffix)
                    if not self.contained(target):
                        die("Refusing to write outside the allowed folders: " + str(target))
                    action = "beside"
            rows.append((path, target, data, digest, action))
        return rows

    def write_all(self, rows):
        total = len(rows)
        beside = []
        for i, (path, target, data, digest, action) in enumerate(rows, 1):
            print("[%d/%d] Writing %s" % (i, total, self.key(path)))
            if action in ("create", "replace", "beside"):
                target.parent.mkdir(parents=True, exist_ok=True)
                with open(target, "wb") as fh:
                    fh.write(data)
            if action == "beside":
                beside.append(self.key(target))
            else:
                self.state[self.key(path)] = digest
        if beside:
            print("Edited files were kept; new versions were written beside them: " + ", ".join(beside))
        return beside

    def save_state(self):
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps(self.state, indent=2), encoding="utf-8")


def sha_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fingerprint(root):
    out = {}
    if root.is_dir():
        for p in sorted(root.rglob("*")):
            if p.is_file():
                out[p.relative_to(root).as_posix()] = sha_file(p)
    return out


def resolve_dirs():
    base = Path(BASE_DIR)
    if not base.is_dir():
        base = Path(__file__).resolve().parent
        print("BASE_DIR was not found, so this script's own folder is used: " + str(base))
    base = base.resolve()
    for proj in (base / base.name, base):
        if (proj / "backend").is_dir():
            return base, proj
    listing = ", ".join(sorted(p.name for p in base.iterdir())) if base.is_dir() else "(missing)"
    die("Run the backend first: main.py, then export_for_frontend.py.\nNo backend folder found under " + str(base) + ". Found: " + listing)


def worker_name(client_id):
    name = re.sub(r"[^a-z0-9-]", "-", str(client_id).lower().replace("_", "-"))
    name = re.sub(r"-+", "-", name).strip("-")[:54].strip("-")
    return name if name and name[0].isalnum() else "dashboard"


def npm_name(client_id):
    name = re.sub(r"[^a-z0-9_-]", "-", str(client_id).lower()).strip("-_")
    return name if name and name[0].isalnum() else "dashboard"


def main():
    base, proj = resolve_dirs()
    backend, frontend, out = proj / "backend", proj / "frontend", proj / "backend" / "output"
    tooling, casefile = base / "_tooling", base / "_casefile"
    contract_file = out / "frontend_contract.json"
    if not contract_file.is_file():
        found = ", ".join(sorted(p.name for p in backend.iterdir())) or "(empty)"
        die("Run the backend first: main.py, then export_for_frontend.py.\nbackend/ currently holds: " + found)
    contract = read_json(contract_file)
    if "__read_error__" in contract:
        die("frontend_contract.json cannot be read: " + contract["__read_error__"])
    project = contract.get("project") if isinstance(contract.get("project"), dict) else {}
    outcomes = contract.get("outcomes") if isinstance(contract.get("outcomes"), dict) else {}
    for need in ("name", "client_id"):
        if not project.get(need):
            die("The contract has no project." + need)
    for need in ("understand", "decide", "monitor"):
        if not isinstance(outcomes.get(need), dict):
            die("The contract has no outcomes." + need)
    version = str(contract.get("schema_version", "1"))
    if version.split(".")[0].isdigit() and int(version.split(".")[0]) > 1:
        print("Note: contract schema version " + version + " is newer than 1; the adapters are tolerant, so the build continues.")
    term_in = contract.get("terminology") if isinstance(contract.get("terminology"), dict) else {}
    missing_terms = [k for k in ("revenue", "customer", "product", "transaction") if not term_in.get(k)]
    if missing_terms:
        print("Notice: terminology is missing " + ", ".join(missing_terms) + "; defaults (Revenue, Customer, Product, Transaction) will be used.")

    # dataset table
    rows, seen = [], set()

    def status_of(rel):
        p = out / rel
        if not p.is_file():
            return "missing"
        data = read_json(p)
        if isinstance(data, dict) and "__read_error__" in data:
            return "invalid"
        if isinstance(data, dict) and data.get("status") == "skipped":
            return "skipped"
        return "ok"

    for name, (group, key, fallback) in FALLBACKS.items():
        rel = (outcomes.get(group) or {}).get(key)
        rel = rel if isinstance(rel, str) and rel.endswith(".json") and ".." not in rel else fallback
        seen.add(rel)
        rows.append((group + "." + key, rel, status_of(rel)))
    for item in contract.get("files") or []:
        rel = item.get("filename") if isinstance(item, dict) else None
        if isinstance(rel, str) and rel not in seen and ".." not in rel:
            seen.add(rel)
            rows.append(("file", rel, status_of(rel)))
    print("\nDatasets")
    for n, p, s in rows:
        print("  %-26s %-40s %s" % (n, p, s.upper() if s != "ok" else "ok"))
    counts = {s: sum(1 for r in rows if r[2] == s) for s in ("ok", "skipped", "missing", "invalid")}
    scorer_rel = next((r[1] for r in rows if r[0] == "monitor.scorer"), None)
    lookup_ok = any(r[0] == "monitor.forecast_lookup" and r[2] == "ok" for r in rows)
    fc = next((r for r in rows if r[0] == "monitor.forecast"), None)
    scorer_state = next((r[2] for r in rows if r[0] == "monitor.scorer"), "missing")
    if scorer_state == "ok":
        sc = read_json(out / scorer_rel)
        mode = "model scoring (" + ("linear" if str(sc.get("type")).lower() == "linear" else "nearest neighbours") + ")"
    elif lookup_ok:
        mode = "lookup table"
    elif fc and fc[2] == "ok" and (read_json(out / fc[1]).get("forecast") if isinstance(read_json(out / fc[1]), dict) else read_json(out / fc[1])):
        mode = "forecast period"
    else:
        mode = "unavailable (no scoring, lookup or forecast data)"
    print("\nPredict page mode for this build: " + mode + "\n")

    # tokens
    domain = str(project.get("domain", "")).lower()
    style = NEUTRAL_STYLE
    for keys, acc, side, head, body in DOMAIN_STYLES:
        if any(k in domain for k in keys):
            style = (acc, side, head, body)
            break
    accent, sidebar, f_head, f_body = style
    a_light, on_light, a_dark, on_dark = accent_pair(accent)
    fams = []
    for f in (f_head, f_body):
        if f not in fams:
            fams.append(f)
    href = "https://fonts.googleapis.com/css2?" + "&amp;".join("family=" + f.replace(" ", "+") + ":wght@400;500;600;700" for f in fams) + "&amp;display=swap"
    font_link = ('    <link rel="preconnect" href="https://fonts.googleapis.com" />\n'
                 '    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />\n'
                 '    <link rel="stylesheet" href="' + href + '" />')
    pname = re.sub(r"\s+", " ", str(project["name"])).strip()
    wname = worker_name(project["client_id"])
    compat = (date.today() - timedelta(days=7)).isoformat()
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", wname) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", compat):
        die("Worker name or compatibility date failed validation")
    letter = next((c for c in pname if c.isalnum()), "D").upper()
    tokens = {
        "__PROJECT_NAME_HTML__": html.escape(pname),
        "__PROJECT_NAME_MD__": pname.replace("\\", "").replace("`", ""),
        "__PROJECT_NAME_JS__": json.dumps(pname),
        "__CLIENT_ID__": npm_name(project["client_id"]),
        "__WORKER_NAME__": wname,
        "__COMPAT_DATE__": compat,
        "__ACCENT_DARK__": a_dark,
        "__ON_ACCENT_DARK__": on_dark,
        "__ACCENT__": a_light,
        "__ON_ACCENT__": on_light,
        "__SIDEBAR__": sidebar,
        "__FONT_HEADING__": f_head,
        "__FONT_BODY__": f_body,
        "__FONT_LINK__": font_link,
        "__LETTER__": html.escape(letter),
    }
    rendered = {rel: render(text, tokens) for rel, text in FILES.items()}
    errors, warns = lint_frontend(rendered)
    for w in warns:
        print("lint warning: " + w)
    if errors:
        print("\nLint found problems; nothing was written:")
        for e in errors:
            print("  ERROR " + e)
        sys.exit(1)
    try:
        import tomllib
        t = tomllib.loads(rendered["wrangler.toml"])
        if set(t) != {"name", "main", "compatibility_date", "assets", "vars"} or set(t["assets"]) != {"directory", "binding", "not_found_handling", "run_worker_first"} or set(t["vars"]) != {"MCP_MODE"}:
            die("wrangler.toml does not have exactly the expected keys")
    except ImportError:
        pass
    json.loads(rendered["package.json"])

    tool_items = [(tooling / name, text) for name, text in TOOLING.items()]
    items = [(frontend / rel, text) for rel, text in rendered.items()] + tool_items
    before = fingerprint(backend)
    writer = Writer(base, [frontend, tooling, casefile])
    plan = writer.plan(items)
    tally = {a: sum(1 for p in plan if p[4] == a) for a in ("create", "replace", "unchanged", "beside")}
    print("Plan: %d to create, %d to replace, %d unchanged, %d to write beside edited files\n" % (tally["create"], tally["replace"], tally["unchanged"], tally["beside"]))
    beside = writer.write_all(plan)

    # data mirror
    target = frontend / "public" / "data"
    if not writer.contained(target) or not target.resolve().as_posix().endswith("frontend/public/data"):
        die("Refusing to refresh an unexpected data folder: " + str(target))
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(out, target)
    print("Copied backend/output into frontend/public/data")

    tooling.mkdir(parents=True, exist_ok=True)
    (tooling / "backend_fingerprint.json").write_text(json.dumps(before, indent=2), encoding="utf-8")
    writer.save_state()

    after = fingerprint(backend)
    if before != after:
        changed = sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))
        die("The backend folder changed during the build: " + ", ".join(changed[:10]))

    node = shutil.which("node")
    if node:
        bad = []
        for rel in rendered:
            if rel.endswith((".js", ".mjs")):
                r = subprocess.run([node, "--check", str(frontend / rel)], capture_output=True, text=True)
                if r.returncode != 0:
                    bad.append(rel + ": " + r.stderr.strip().split("\n")[0])
        if bad:
            print("node --check failed:")
            for b in bad:
                print("  ERROR " + b)
            sys.exit(1)
        print("node --check passed for every .js and .mjs file")
    else:
        print("node was not found, so the syntax check was skipped; npm run check will validate the data")

    print("\nDatasets again: %d loaded, %d skipped, %d missing, %d invalid" % (counts["ok"], counts["skipped"], counts["missing"], counts["invalid"]))
    print("\nFrontend build complete.")
    print("  Project        : %s   (%s)" % (pname, project.get("domain", "")))
    print("  Worker name    : " + wname)
    print("  Datasets       : %d loaded, %d skipped, %d missing" % (counts["ok"], counts["skipped"], counts["missing"] + counts["invalid"]))
    print("  Files written  : %d   (beside existing edited files: %d)" % (tally["create"] + tally["replace"] + tally["beside"], len(beside)))
    print("  Backend        : unchanged (fingerprint verified)")
    print("  MCP            : off  (edit MCP_MODE in wrangler.toml: token or open)")
    print("  Data access    : files in public/data are public to anyone who can open the site; use an access policy for real client data")
    rel_front = frontend.relative_to(base)
    print("\nNext steps (inside %s):" % rel_front)
    for line in ("npm install", "npm run check", "npm run dev", "npm run build", "npx wrangler login        (first time only)", "npm run deploy"):
        print("  " + line)
    print("\nThen, from %s:" % base)
    print("  python _tooling/finish_frontend.py")
    print("  (read _casefile/frontend_audit_report.txt, then delete generate_react_frontend.py and _tooling)")


if __name__ == "__main__":
    main()