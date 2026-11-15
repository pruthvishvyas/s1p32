import { createContext, useCallback, useContext, useMemo } from 'react';
import { useContract } from '../hooks/useContract.js';
import { humanize } from '../utils/adapters.js';
import { pluralize } from '../utils/text.js';

const DEFAULTS = { revenue: 'Revenue', customer: 'Customer', product: 'Product', transaction: 'Transaction' };
const TerminologyContext = createContext(DEFAULTS);

export function TerminologyProvider({ children }) {
  const contract = useContract();
  const terms = useMemo(() => ({ ...DEFAULTS, ...(contract.data ? contract.data.terminology : {}) }), [contract.data]);
  return <TerminologyContext.Provider value={terms}>{children}</TerminologyContext.Provider>;
}

export function useTerm() {
  const terms = useContext(TerminologyContext);
  return useCallback((key, options) => {
    const opts = options || {};
    let word = terms[key] || humanize(key);
    if (opts.plural) word = pluralize(word);
    return opts.lower ? word.toLowerCase() : word;
  }, [terms]);
}
