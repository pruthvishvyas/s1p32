import { SkeletonCard } from './SkeletonCard.jsx';
import { refreshHint } from '../../utils/text.js';

export function DataState({ query, label, skeleton }) {
  if (query.loading) return skeleton || <SkeletonCard count={2} height={96} />;
  const err = query.error;
  if (!err) return null;
  const retry = <button type="button" className="btn-secondary" onClick={query.reload}>Retry</button>;
  let body;
  switch (err.kind) {
    case 'skipped':
      body = <p>{'This section was skipped: ' + err.message}</p>;
      break;
    case 'missing':
    case 'empty':
      body = (
        <div>
          <p>{'No ' + label + ' yet. ' + refreshHint()}</p>
          {retry}
        </div>
      );
      break;
    case 'network':
      body = (
        <div>
          <p>{'Could not load ' + label + '. Check the connection.'}</p>
          {retry}
        </div>
      );
      break;
    default:
      body = (
        <div>
          <p>{'The ' + label + ' file is not in the expected format.'}</p>
          <p className="muted small">{err.message}</p>
        </div>
      );
  }
  return <div className="card state-box" role="status">{body}</div>;
}
