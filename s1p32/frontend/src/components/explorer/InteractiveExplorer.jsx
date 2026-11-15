import { useEffect, useMemo, useState } from 'react';
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
