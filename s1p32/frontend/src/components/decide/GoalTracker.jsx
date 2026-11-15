import { useEffect, useState } from 'react';
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
