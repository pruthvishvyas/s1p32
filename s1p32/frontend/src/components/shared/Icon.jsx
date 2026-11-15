const PATHS = {
  sun: 'M12 4V2M12 22v-2M4 12H2M22 12h-2M5.6 5.6 4.2 4.2M19.8 19.8l-1.4-1.4M5.6 18.4l-1.4 1.4M19.8 4.2l-1.4 1.4M12 8a4 4 0 100 8 4 4 0 000-8z',
  moon: 'M21 12.8A9 9 0 1111.2 3a7 7 0 009.8 9.8z',
  up: 'M12 19V5M5 12l7-7 7 7',
  down: 'M12 5v14M19 12l-7 7-7-7',
  flat: 'M5 12h14',
  overview: 'M3 3h7v9H3zM14 3h7v5h-7zM14 12h7v9h-7zM3 16h7v5H3z',
  segments: 'M12 3a9 9 0 109 9h-9z',
  anomalies: 'M12 3l10 18H2zM12 10v5M12 18v.5',
  insights: 'M9 18h6M10 21h4M12 3a6 6 0 00-4 10.5c.7.7 1 1.5 1 2.5h6c0-1 .3-1.8 1-2.5A6 6 0 0012 3z',
  recommendations: 'M5 12l4 4 10-10',
  whatif: 'M4 6h16M4 12h16M4 18h16M8 4v4M16 10v4M10 16v4',
  goals: 'M12 12m-9 0a9 9 0 1018 0 9 9 0 10-18 0M12 12m-4 0a4 4 0 108 0 4 4 0 10-8 0M12 12h.01',
  forecast: 'M3 17l6-6 4 4 8-8M15 7h6v6',
  predict: 'M4 20V10M10 20V4M16 20v-8M22 20H2',
  progress: 'M4 12h16M4 6h10M4 18h13',
  alerts: 'M18 8a6 6 0 10-12 0c0 7-3 9-3 9h18s-3-2-3-9M10 21h4',
  explore: 'M11 4a7 7 0 100 14 7 7 0 000-14zM21 21l-4.3-4.3',
  guide: 'M4 4h12a4 4 0 014 4v12H8a4 4 0 01-4-4zM8 8h8M8 12h8',
  health: 'M3 12h4l3-8 4 16 3-8h4',
  close: 'M6 6l12 12M18 6L6 18',
};

export function Icon({ name, label }) {
  const d = PATHS[name] || PATHS.flat;
  return (
    <svg className="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden={label ? undefined : 'true'} role={label ? 'img' : undefined} aria-label={label || undefined}>
      <path d={d} />
    </svg>
  );
}
