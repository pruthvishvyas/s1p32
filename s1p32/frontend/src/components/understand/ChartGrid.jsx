import { useDataset } from '../../hooks/useDataset.js';
import { DataState } from '../shared/DataState.jsx';
import { SkeletonCard } from '../shared/SkeletonCard.jsx';
import { ErrorBoundary } from '../shared/ErrorBoundary.jsx';
import { ChartPanel } from './ChartPanel.jsx';

export function ChartGrid() {
  const query = useDataset('charts');
  if (query.loading || query.error) {
    return <DataState query={query} label="charts" skeleton={<SkeletonCard count={2} height={352} />} />;
  }
  const charts = query.data;
  return (
    <div className="grid chart-grid">
      {charts.map((chart, i) => (
        <ErrorBoundary key={chart.id + '-' + i} label={chart.title}>
          <ChartPanel chart={chart} />
        </ErrorBoundary>
      ))}
    </div>
  );
}
