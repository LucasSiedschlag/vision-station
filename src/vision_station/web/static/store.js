// A tiny observable store, so any screen can read and react to shared state.
import { useState, useEffect } from './lib.js';

export function createStore(initial) {
  let value = initial;
  const listeners = new Set();
  return {
    get: () => value,
    set(next) {
      value = typeof next === 'function' ? next(value) : next;
      listeners.forEach((fn) => fn(value));
    },
    subscribe(fn) {
      listeners.add(fn);
      return () => listeners.delete(fn);
    },
  };
}

export function useStore(store) {
  const [value, setValue] = useState(store.get());
  useEffect(() => store.subscribe(setValue), [store]);
  return value;
}
