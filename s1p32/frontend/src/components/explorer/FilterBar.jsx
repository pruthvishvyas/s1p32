import { useExplorer } from '../../context/ExplorerContext.jsx';

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
