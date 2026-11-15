export function formatKind(unit) {
  const u = String(unit || '').toLowerCase();
  if (u === 'currency' || u === 'percent' || u === 'integer') return u;
  return 'decimal';
}

export function createFormatter(locale, currency) {
  const loc = locale || 'en-US';
  const makeNumber = opts => {
    try { return new Intl.NumberFormat(loc, opts); } catch { return new Intl.NumberFormat('en-US', opts); }
  };
  let money = null;
  try {
    if (currency && currency.code) money = new Intl.NumberFormat(loc, { style: 'currency', currency: currency.code, maximumFractionDigits: 0 });
  } catch { money = null; }
  const whole = makeNumber({ maximumFractionDigits: 0 });
  const decimal = makeNumber({ maximumFractionDigits: 2 });
  const oneDecimal = makeNumber({ minimumFractionDigits: 1, maximumFractionDigits: 1 });
  const compactFmt = makeNumber({ notation: 'compact', maximumFractionDigits: 1 });
  let dateFmt;
  try { dateFmt = new Intl.DateTimeFormat(loc, { dateStyle: 'medium' }); } catch { dateFmt = new Intl.DateTimeFormat('en-US', { dateStyle: 'medium' }); }
  let rel = null;
  try { rel = new Intl.RelativeTimeFormat(loc, { numeric: 'auto' }); } catch { rel = null; }

  const toNumber = v => (typeof v === 'number' ? v : Number(v));

  function value(v, format) {
    if (v === null || v === undefined || v === '') return '-';
    if (format === 'text') return String(v);
    const n = toNumber(v);
    if (!Number.isFinite(n)) return String(v);
    switch (format) {
      case 'currency':
        if (money) return money.format(n);
        return (currency && currency.symbol ? currency.symbol : '') + whole.format(n);
      case 'percent': return oneDecimal.format(n) + '%';
      case 'integer': return whole.format(n);
      default: return decimal.format(n);
    }
  }

  function compact(v) {
    const n = toNumber(v);
    return Number.isFinite(n) ? compactFmt.format(n) : String(v);
  }

  function percent(v) { return value(v, 'percent'); }

  function date(iso) {
    const d = new Date(iso);
    return Number.isNaN(d.getTime()) ? String(iso === null || iso === undefined ? '' : iso) : dateFmt.format(d);
  }

  function ago(iso) {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return String(iso === null || iso === undefined ? '' : iso);
    const seconds = Math.round((d.getTime() - Date.now()) / 1000);
    const steps = [['year', 31536000], ['month', 2592000], ['day', 86400], ['hour', 3600], ['minute', 60]];
    for (const [unit, size] of steps) {
      if (Math.abs(seconds) >= size) {
        const count = Math.round(seconds / size);
        return rel ? rel.format(count, unit) : Math.abs(count) + ' ' + unit + 's ago';
      }
    }
    return 'just now';
  }

  return { value, compact, percent, date, ago };
}
