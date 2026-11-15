import { useState } from 'react';
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
