export function PageSection({ title, intro, children }) {
  return (
    <section className="page-section">
      <header className="page-head">
        <h1>{title}</h1>
        {intro ? <p className="muted">{intro}</p> : null}
      </header>
      {children}
    </section>
  );
}
