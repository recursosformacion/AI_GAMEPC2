// Frontera "Support" del frontend: único punto por el que Chorus/osap-app conocerá la
// relación de apoyo. En el MVP usa `LocalSupportGateway` (derivado de Auth).
// Cuando exista osap-support, se sustituye la implementación sin tocar las apps.

export type { SupportGateway, SupportStatus, SupportSummary } from "./supportGateway";
export { supportGateway, useSupport } from "./localSupportGateway";
