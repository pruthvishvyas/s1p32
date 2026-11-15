import { useDataset } from '../../hooks/useDataset.js';
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
