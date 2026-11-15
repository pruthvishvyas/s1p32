import { useDataset } from '../../hooks/useDataset.js';
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
