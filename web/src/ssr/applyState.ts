import { useComposers } from "../state/composers";
import { usePreferences } from "../state/preferences";
import { usePublicWork } from "../state/publicWork";
import { useSystem } from "../state/system";
import type { SsrState } from "./types";

/** Aplica el estado precargado por el servidor antes de renderizar o hidratar. */
export function applySsrState(state: SsrState | undefined): void {
  if (!state) return;
  usePreferences.setState({ lang: state.lang, dark: state.dark });
  if (state.composers !== undefined) useComposers.setState(state.composers);
  if (state.system?.health !== undefined) useSystem.setState({ health: state.system.health });
  if (state.publicWork !== undefined) {
    usePublicWork.setState({
      sheet: state.publicWork.sheet,
      status: state.publicWork.status,
      loadedId: state.publicWork.sheet?.work.work_id ?? null,
    });
  }
}
