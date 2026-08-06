import { Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "../layouts/Layout";
import { DashboardPage } from "../pages/DashboardPage";
import { JobsPage } from "../pages/JobsPage";
import { FactsPage, ObservationsPage, SuggestionsPage } from "../pages/KnowledgePages";
import { ProvidersPage } from "../pages/ProvidersPage";
import { SearchesPage } from "../pages/SearchesPage";

// Routing is independent of navigation: navigation is a consequence of these routes.
export function AppRoutes() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/searches" element={<SearchesPage />} />
        <Route path="/jobs" element={<JobsPage />} />
        <Route path="/knowledge" element={<Navigate to="/knowledge/observations" replace />} />
        <Route path="/knowledge/observations" element={<ObservationsPage />} />
        <Route path="/knowledge/facts" element={<FactsPage />} />
        <Route path="/knowledge/suggestions" element={<SuggestionsPage />} />
        <Route path="/providers" element={<ProvidersPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
