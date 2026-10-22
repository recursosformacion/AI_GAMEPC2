import { useSyncExternalStore } from "react";
import { createStore, type StateCreator, type StoreApi } from "zustand/vanilla";

type SelectorHook<T> = {
  (): T;
  <U>(selector: (state: T) => U): U;
};

/**
 * Store de Zustand con snapshot de servidor = estado actual.
 *
 * El `useStore` de Zustand usa `getInitialState` como snapshot de servidor; si el SSR
 * precarga con `setState`, el HTML seguiría pintando el estado inicial vacío. Este hook
 * usa `getState` tanto en cliente como en servidor, de modo que el estado precargado es
 * el que se renderiza y el que se usa al hidratar.
 */
export function createSsrStore<T>(
  creator: StateCreator<T>,
): SelectorHook<T> & StoreApi<T> {
  const api = createStore(creator);
  const useStore = (<U>(selector?: (state: T) => U): T | U => {
    const select = selector ?? ((state: T) => state as unknown as U);
    return useSyncExternalStore(
      api.subscribe,
      () => select(api.getState()),
      () => select(api.getState()),
    );
  }) as SelectorHook<T>;
  return Object.assign(useStore, api) as SelectorHook<T> & StoreApi<T>;
}
