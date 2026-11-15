import { createContext, useCallback, useContext, useMemo, useState } from 'react';

const ExplorerContext = createContext(null);

export function ExplorerProvider({ children }) {
  const [filters, setFilters] = useState({});
  const [metricKey, setMetricKey] = useState(null);

  const setFilter = useCallback((dim, value, toggle = true) => {
    setFilters(prev => {
      const next = { ...prev };
      if (!value || (toggle && prev[dim] === value)) delete next[dim];
      else next[dim] = value;
      return next;
    });
  }, []);
  const clearFilters = useCallback(() => setFilters({}), []);
  const activeCount = Object.keys(filters).length;

  const value = useMemo(
    () => ({ filters, setFilter, clearFilters, metricKey, setMetricKey, activeCount }),
    [filters, setFilter, clearFilters, metricKey, activeCount],
  );
  return <ExplorerContext.Provider value={value}>{children}</ExplorerContext.Provider>;
}

export function useExplorer() {
  const ctx = useContext(ExplorerContext);
  if (!ctx) throw new Error('Explorer controls need the explorer provider around them');
  return ctx;
}
