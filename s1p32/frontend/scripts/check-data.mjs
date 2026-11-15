import fs from 'node:fs';
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
