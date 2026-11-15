export function SkeletonCard({ count = 1, height = 96 }) {
  const items = Array.from({ length: count }, (_, i) => i);
  return (
    <div className="grid" aria-busy="true" aria-label="Loading">
      {items.map(i => (
        <div className="card skeleton" key={'sk-' + i} style={{ height: (height / 16) + 'rem' }} />
      ))}
    </div>
  );
}
