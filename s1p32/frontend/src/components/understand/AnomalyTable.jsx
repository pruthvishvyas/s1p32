import { useMemo, useState } from 'react';
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
