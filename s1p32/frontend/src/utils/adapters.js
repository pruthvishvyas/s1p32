import { DataError } from './errors.js';

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
