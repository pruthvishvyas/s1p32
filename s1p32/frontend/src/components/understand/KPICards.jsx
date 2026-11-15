import { useDataset } from '../../hooks/useDataset.js';
import { useFormat } from '../../context/FormatContext.jsx';
import { DataState } from '../shared/DataState.jsx';
import { SkeletonCard } from '../shared/SkeletonCard.jsx';
import { Icon } from '../shared/Icon.jsx';

export function KPICards() {
  const query = useDataset('kpis');
  const fmt = useFormat();
  if (query.loading || query.error) {
    return <DataState query={query} label="key numbers" skeleton={<SkeletonCard count={4} height={112} />} />;
  }
  const items = query.data;
  return (
    <div className="grid kpi-grid">
      {items.map(k => (
        <article className="card kpi" key={k.key}>
          <p className="kpi-label">{k.label}</p>
          <p className="kpi-value">{fmt.value(k.value, k.format)}</p>
          {k.trend !== null ? (
            <p className="kpi-trend">
              <Icon name={k.trend > 0 ? 'up' : k.trend < 0 ? 'down' : 'flat'} />
              <span>{(k.trend > 0 ? '+' : '') + fmt.value(k.trend, 'percent') + ' vs previous period'}</span>
            </p>
          ) : null}
          {k.note ? <p className="muted small">{k.note}</p> : null}
        </article>
      ))}
    </div>
  );
}
