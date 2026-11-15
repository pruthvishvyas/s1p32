import { createContext, useContext, useMemo } from 'react';
import { useDataset } from '../hooks/useDataset.js';
import { createFormatter } from '../utils/formatters.js';

const FormatContext = createContext(createFormatter('en-US', null));

export function FormatProvider({ children }) {
  const summary = useDataset('summary');
  const fmt = useMemo(() => {
    const s = summary.data;
    return createFormatter(s ? s.locale : 'en-US', s ? s.currency : null);
  }, [summary.data]);
  return <FormatContext.Provider value={fmt}>{children}</FormatContext.Provider>;
}

export function useFormat() {
  return useContext(FormatContext);
}
