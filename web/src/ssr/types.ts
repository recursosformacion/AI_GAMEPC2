import type {
  ComposerDetail,
  ComposerList,
  ComposerWorks,
  ComposerIndexWorks,
  PublicWork,
  SystemHealth,
} from "../api/types";
import type { Language } from "../i18n/translations";

/** Estado que el servidor serializa en el HTML y el cliente reutiliza antes de hidratar. */
export interface SsrState {
  lang: Language;
  dark: boolean;
  composers?: {
    list?: ComposerList;
    biography?: ComposerDetail;
    works?: ComposerWorks;
    indexWorks?: ComposerIndexWorks;
    q?: string;
    lastQuery?: string;
    lastOffset?: number;
    worksFor?: string;
    indexWorksFor?: string;
  };
  system?: { health?: SystemHealth };
  publicWork?: { sheet: PublicWork | null; status: "ok" | "missing" | "loading" };
}

declare global {
  interface Window {
    __OSAP_STATE__?: SsrState;
    __OSAP_SSR_PATH__?: string;
  }
}
