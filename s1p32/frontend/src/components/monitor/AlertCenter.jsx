import { useState } from 'react';
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
