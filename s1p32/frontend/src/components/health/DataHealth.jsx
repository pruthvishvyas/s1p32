import { useDataset } from '../../hooks/useDataset.js';
import { useContract } from '../../hooks/useContract.js';
import { useFormat } from '../../context/FormatContext.jsx';
import { DataState } from '../shared/DataState.jsx';
import { SkeletonCard } from '../shared/SkeletonCard.jsx';
import { DATASETS } from '../../utils/datasets.js';
import { predictMode } from '../../utils/predict.js';

function DatasetRow({ name }) {
  const q = useDataset(name);
  let state = 'Loaded';
  let cls = 'status status-ok';
  if (q.loading) { state = 'Loading'; cls = 'status status-none'; }
  else if (q.error) {
    state = q.error.kind === 'skipped' ? 'Skipped: ' + q.error.message : q.error.kind === 'missing' || q.error.kind === 'empty' ? 'Missing' : 'Invalid: ' + q.error.message;
    cls = q.error.kind === 'skipped' ? 'status status-warn' : 'status status-bad';
  }
  return <tr><th scope="row">{name}</th><td><span className={cls}>{state}</span></td></tr>;
}

function PredictModeLine() {
  const scorer = useDataset('scorer');
  const lookup = useDataset('forecastLookup');
  const forecast = useDataset('forecast');
  if (scorer.loading || lookup.loading || forecast.loading) return <p className="muted">Checking the Predict page.</p>;
  return <p>{'Predict page mode: ' + predictMode(scorer, lookup, forecast)}</p>;
}

function Overview() {
  const query = useDataset('summary');
  const contract = useContract();
  const fmt = useFormat();
  if (query.loading || query.error) {
    return <DataState query={query} label="summary" skeleton={<SkeletonCard count={2} height={120} />} />;
  }
  const s = query.data;
  return (
    <section className="card">
      <h2>Last run</h2>
      <dl className="detail-list">
        <div className="detail-pair"><dt>Updated</dt><dd>{s.lastRun ? fmt.ago(s.lastRun) + ' (' + fmt.date(s.lastRun) + ')' : '-'}</dd></div>
        <div className="detail-pair"><dt>Data source</dt><dd>{s.source || '-'}</dd></div>
        <div className="detail-pair"><dt>Rows</dt><dd>{fmt.value(s.rows, 'integer')}</dd></div>
        <div className="detail-pair"><dt>Date range</dt><dd>{s.dateRange.start ? fmt.date(s.dateRange.start) + ' to ' + fmt.date(s.dateRange.end) : '-'}</dd></div>
        <div className="detail-pair"><dt>Contract version</dt><dd>{contract.data ? contract.data.schemaVersion : '-'}</dd></div>
      </dl>
    </section>
  );
}

function RunStages() {
  const query = useDataset('runLog');
  if (query.loading || query.error) {
    return <DataState query={query} label="run log" skeleton={<SkeletonCard count={1} height={120} />} />;
  }
  const run = query.data[0];
  if (!run) return <div className="card state-box"><p>No runs are recorded yet.</p></div>;
  return (
    <section className="card table-card">
      <h2>Latest run steps</h2>
      <div className="table-scroll">
        <table className="data-table">
          <thead><tr><th scope="col">Step</th><th scope="col">Status</th><th scope="col">Seconds</th><th scope="col">Reason</th></tr></thead>
          <tbody>
            {run.stages.map((st, i) => (
              <tr key={st.name + '-' + i}><th scope="row">{st.name}</th><td>{st.status}</td><td>{st.seconds === null ? '-' : st.seconds}</td><td>{st.reason || '-'}</td></tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export function DataHealth() {
  return (
    <div className="stack">
      <Overview />
      <RunStages />
      <section className="card table-card">
        <h2>Data files</h2>
        <PredictModeLine />
        <div className="table-scroll">
          <table className="data-table">
            <thead><tr><th scope="col">Dataset</th><th scope="col">State</th></tr></thead>
            <tbody>
              {Object.keys(DATASETS).map(name => <DatasetRow key={name} name={name} />)}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
