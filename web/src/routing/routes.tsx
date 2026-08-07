import { Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "../layouts/Layout";
import { CandidatesPage } from "../pages/CandidatesPage";
import { ComposerPage } from "../pages/ComposerPage";
import { DiscoverPage } from "../pages/DiscoverPage";
import { HomePage } from "../pages/HomePage";
import { JobsPage } from "../pages/JobsPage";
import { FactsPage, ObservationsPage, SuggestionsPage } from "../pages/KnowledgePages";
import { ProvidersPage } from "../pages/ProvidersPage";
import { SearchStudioPage } from "../pages/SearchStudioPage";
import { SourceCatalogPage } from "../pages/SourceCatalogPage";
import { SourcesPage } from "../pages/SourcesPage";
import { WorkResolutionPage } from "../pages/WorkResolutionPage";

// Routing is independent of navigation: navigation is a consequence of these routes.
export function AppRoutes() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<HomePage />} />
        <Route path="/discover" element={<DiscoverPage />} />
        <Route path="/catalog" element={<SourceCatalogPage />} />
        <Route path="/sources" element={<SourcesPage />} />
        <Route path="/studio" element={<SearchStudioPage />} />
        <Route path="/composer" element={<ComposerPage />} />
        <Route path="/candidates" element={<CandidatesPage />} />
        <Route path="/resolution" element={<WorkResolutionPage />} />
        <Route path="/knowledge" element={<Navigate to="/knowledge/observations" replace />} />
        <Route path="/knowledge/observations" element={<ObservationsPage />} />
        <Route path="/knowledge/facts" element={<FactsPage />} />
        <Route path="/knowledge/suggestions" element={<SuggestionsPage />} />
        <Route path="/providers" element={<ProvidersPage />} />
        <Route path="/jobs" element={<JobsPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
