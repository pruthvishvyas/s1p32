import { useState } from 'react';
import { useDataset } from '../../hooks/useDataset.js';
import { useFormat } from '../../context/FormatContext.jsx';
import { DataState } from '../shared/DataState.jsx';
import { SkeletonCard } from '../shared/SkeletonCard.jsx';
import { DrillDownPanel } from '../explorer/DrillDownPanel.jsx';
import { BarBlock } from './ChartPanel.jsx';
import { humanize } from '../../utils/adapters.js';

export function SegmentExplorer() {
  const query = useDataset('segments');
  if (query.loading || query.error) {
    return <DataState query={query} label="segments" skeleton={<SkeletonCard count={3} height={140} />} />;
  }
  return <SegmentBody segments={query.data} />;
}

function SegmentBody({ segments }) {
  const fmt = useFormat();
  const [open, setOpen] = useState(null);
  const chosen = segments.items.find(s => s.name === open) || null;
  const sizeRows = segments.items.map(s => ({ label: s.name, value: s.size }));
  return (
    <div className="stack">
      {segments.method ? <p className="muted">{'Method: ' + segments.method}</p> : null}
      <div className="grid">
        {segments.items.map(s => (
          <button type="button" className="card segment-card" key={s.name} onClick={() => setOpen(s.name)}>
            <span className="segment-name">{s.name}</span>
            <span className="kpi-value">{fmt.value(s.size, 'integer')}</span>
            <span className="bar-track" aria-hidden="true"><span className="bar-fill" style={{ width: Math.min(100, Math.max(0, s.share)) + '%' }} /></span>
            <span className="muted small">{fmt.value(s.share, 'percent') + ' of the total'}</span>
          </button>
        ))}
      </div>
      <section className="card chart-card">
        <h3>Segment sizes</h3>
        <div className="chart-box"><BarBlock rows={sizeRows} format="integer" name="Size" /></div>
      </section>
      {chosen ? (
        <DrillDownPanel title={chosen.name} onClose={() => setOpen(null)}>
          {chosen.description ? <p>{chosen.description}</p> : null}
          <dl className="detail-list">
            <dt>Size</dt><dd>{fmt.value(chosen.size, 'integer')}</dd>
            <dt>Share</dt><dd>{fmt.value(chosen.share, 'percent')}</dd>
            {Object.entries(chosen.summary).map(([k, v]) => (
              <div className="detail-pair" key={k}><dt>{humanize(k)}</dt><dd>{fmt.value(v, 'decimal')}</dd></div>
            ))}
          </dl>
        </DrillDownPanel>
      ) : null}
    </div>
  );
}
