import {
  useCatalogues,
  useEnsembles,
  useGenres,
  useInstrumentCategories,
  useInstruments,
} from "../state/classification";
import { useComposers } from "../state/composers";
import { useEpochs } from "../state/epochs";
import { usePreferences } from "../state/preferences";
import { usePublicWork } from "../state/publicWork";
import { useSystem } from "../state/system";
import { setSsrClassification } from "./classification";
import type { SsrState } from "./types";

/** Aplica el estado precargado por el servidor antes de renderizar o hidratar. */
export function applySsrState(state: SsrState | undefined): void {
  if (!state) return;
  setSsrClassification(state.classification);
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
  if (state.classification?.genres !== undefined) {
    useGenres.setState({ data: state.classification.genres, loading: false, error: null });
  }
  if (state.classification?.catalogues !== undefined) {
    useCatalogues.setState({ data: state.classification.catalogues, loading: false, error: null });
  }
  if (state.classification?.instruments !== undefined) {
    useInstruments.setState({ data: state.classification.instruments, loading: false, error: null });
  }
  if (state.classification?.instrumentCategories !== undefined) {
    useInstrumentCategories.setState({
      data: state.classification.instrumentCategories,
      loading: false,
      error: null,
    });
  }
  if (state.classification?.ensembles !== undefined) {
    useEnsembles.setState({ data: state.classification.ensembles, loading: false, error: null });
  }
  if (state.classification?.epochs !== undefined) {
    useEpochs.setState({ data: state.classification.epochs, loading: false, error: null });
  }
}
