import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "../layouts/Layout";
import { AdminLayout } from "../layouts/AdminLayout";
import { HomePage } from "../pages/HomePage";

// Las páginas se cargan por chunk (code-splitting): reduce el bundle inicial y mejora LCP/INP.
// La portada (HomePage) y los layouts van eager (primer render).
const AboutPage = lazy(() => import("../pages/AboutPage").then((m) => ({ default: m.AboutPage })));
const ActivityPage = lazy(() => import("../pages/ActivityPage").then((m) => ({ default: m.ActivityPage })));
const AdminComposerDetailPage = lazy(() => import("../pages/AdminComposerDetailPage").then((m) => ({ default: m.AdminComposerDetailPage })));
const AdminComposersPage = lazy(() => import("../pages/AdminComposersPage").then((m) => ({ default: m.AdminComposersPage })));
const AdminSourceSuggestionsPage = lazy(() => import("../pages/AdminSourceSuggestionsPage").then((m) => ({ default: m.AdminSourceSuggestionsPage })));
const AdminProvidersPage = lazy(() => import("../pages/AdminProvidersPage").then((m) => ({ default: m.AdminProvidersPage })));
const AdminCorrectionsPage = lazy(() => import("../pages/AdminCorrectionsPage").then((m) => ({ default: m.AdminCorrectionsPage })));
const AdminFunnelPage = lazy(() => import("../pages/AdminFunnelPage").then((m) => ({ default: m.AdminFunnelPage })));
const AdminUserDetailPage = lazy(() => import("../pages/AdminUserDetailPage").then((m) => ({ default: m.AdminUserDetailPage })));
const AdminUsersPage = lazy(() => import("../pages/AdminUsersPage").then((m) => ({ default: m.AdminUsersPage })));
const AdminWorkPersonAiPage = lazy(() => import("../pages/AdminWorkPersonAiPage").then((m) => ({ default: m.AdminWorkPersonAiPage })));
const AdminPaymentsPage = lazy(() => import("../pages/AdminPaymentsPage").then((m) => ({ default: m.AdminPaymentsPage })));
const AdminPage = lazy(() => import("../pages/AdminPage").then((m) => ({ default: m.AdminPage })));
const AdminQuotaPage = lazy(() => import("../pages/AdminQuotaPage").then((m) => ({ default: m.AdminQuotaPage })));
const AliasPage = lazy(() => import("../pages/AliasPage").then((m) => ({ default: m.AliasPage })));
const AuthCallbackPage = lazy(() => import("../pages/AuthCallbackPage").then((m) => ({ default: m.AuthCallbackPage })));
const CollaboratorsPage = lazy(() => import("../pages/CollaboratorsPage").then((m) => ({ default: m.CollaboratorsPage })));
const HowItWorksPage = lazy(() => import("../pages/HowItWorksPage").then((m) => ({ default: m.HowItWorksPage })));
const CandidatesPage = lazy(() => import("../pages/CandidatesPage").then((m) => ({ default: m.CandidatesPage })));
const ComposerDetailPage = lazy(() => import("../pages/ComposerDetailPage").then((m) => ({ default: m.ComposerDetailPage })));
const ComposerPage = lazy(() => import("../pages/ComposerPage").then((m) => ({ default: m.ComposerPage })));
const CataloguesPage = lazy(() => import("../pages/CataloguesPage").then((m) => ({ default: m.CataloguesPage })));
const ComposersPage = lazy(() => import("../pages/ComposersPage").then((m) => ({ default: m.ComposersPage })));
const DiscoverPage = lazy(() => import("../pages/DiscoverPage").then((m) => ({ default: m.DiscoverPage })));
const EnsemblesPage = lazy(() => import("../pages/EnsemblesPage").then((m) => ({ default: m.EnsemblesPage })));
const EpochsPage = lazy(() => import("../pages/EpochsPage").then((m) => ({ default: m.EpochsPage })));
const GenresPage = lazy(() => import("../pages/GenresPage").then((m) => ({ default: m.GenresPage })));
const InstrumentsPage = lazy(() => import("../pages/InstrumentsPage").then((m) => ({ default: m.InstrumentsPage })));
const ExplorePage = lazy(() => import("../pages/ExplorePage").then((m) => ({ default: m.ExplorePage })));
const ViewerPage = lazy(() => import("../pages/ViewerPage").then((m) => ({ default: m.ViewerPage })));
const JobsPage = lazy(() => import("../pages/JobsPage").then((m) => ({ default: m.JobsPage })));
const FactsPage = lazy(() => import("../pages/KnowledgePages").then((m) => ({ default: m.FactsPage })));
const ObservationsPage = lazy(() => import("../pages/KnowledgePages").then((m) => ({ default: m.ObservationsPage })));
const SuggestionsPage = lazy(() => import("../pages/KnowledgePages").then((m) => ({ default: m.SuggestionsPage })));
const ProvidersPage = lazy(() => import("../pages/ProvidersPage").then((m) => ({ default: m.ProvidersPage })));
const SearchStudioPage = lazy(() => import("../pages/SearchStudioPage").then((m) => ({ default: m.SearchStudioPage })));
const SourceCatalogPage = lazy(() => import("../pages/SourceCatalogPage").then((m) => ({ default: m.SourceCatalogPage })));
const SourcesPage = lazy(() => import("../pages/SourcesPage").then((m) => ({ default: m.SourcesPage })));
const SupportOsapPage = lazy(() => import("../pages/SupportOsapPage").then((m) => ({ default: m.SupportOsapPage })));
const CorrectionsPage = lazy(() => import("../pages/CorrectionsPage").then((m) => ({ default: m.CorrectionsPage })));
const WorkResolutionPage = lazy(() => import("../pages/WorkResolutionPage").then((m) => ({ default: m.WorkResolutionPage })));
const CookiePolicyPage = lazy(() => import("../pages/legal/LegalPages").then((m) => ({ default: m.CookiePolicyPage })));
const LegalNoticePage = lazy(() => import("../pages/legal/LegalPages").then((m) => ({ default: m.LegalNoticePage })));
const PrivacyPolicyPage = lazy(() => import("../pages/legal/LegalPages").then((m) => ({ default: m.PrivacyPolicyPage })));

// Routing is independent of navigation: navigation is a consequence of these routes.
export function AppRoutes() {
  return (
    <Suspense fallback={null}>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<HomePage />} />
          <Route path="/explore" element={<ExplorePage />} />
          <Route path="/oidc/callback" element={<AuthCallbackPage />} />
          <Route path="/discover" element={<DiscoverPage />} />
          <Route path="/support" element={<SupportOsapPage />} />
          <Route path="/corrections" element={<CorrectionsPage />} />
          <Route path="/catalog" element={<SourceCatalogPage />} />
          <Route path="/sources" element={<SourcesPage />} />
          <Route path="/studio" element={<SearchStudioPage />} />
          <Route path="/composer" element={<ComposerPage />} />
          <Route path="/composers" element={<ComposersPage />} />
          <Route path="/epochs" element={<EpochsPage />} />
          <Route path="/genres" element={<GenresPage />} />
          <Route path="/catalogues" element={<CataloguesPage />} />
          <Route path="/instruments" element={<InstrumentsPage />} />
          <Route path="/ensembles" element={<EnsemblesPage />} />
          <Route path="/activity" element={<ActivityPage />} />
          <Route path="/composers/:personId" element={<ComposerDetailPage />} />
          <Route path="/about" element={<AboutPage />} />
          <Route path="/about/how-it-works" element={<HowItWorksPage />} />
          <Route path="/aviso-legal" element={<LegalNoticePage />} />
          <Route path="/privacidad" element={<PrivacyPolicyPage />} />
          <Route path="/cookies" element={<CookiePolicyPage />} />
          <Route path="/viewer" element={<ViewerPage />} />
          <Route path="/collaborators" element={<CollaboratorsPage />} />
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
        <Route element={<AdminLayout />}>
          <Route path="/admin" element={<AdminPage />} />
          <Route path="/admin/users" element={<AdminUsersPage />} />
          <Route path="/admin/payments" element={<AdminPaymentsPage />} />
          <Route path="/admin/users/:userId" element={<AdminUserDetailPage />} />
          <Route path="/admin/composers" element={<AdminComposersPage />} />
          <Route path="/admin/composers/:personId" element={<AdminComposerDetailPage />} />
          <Route path="/admin/aliases" element={<AliasPage />} />
          <Route path="/admin/source-suggestions" element={<AdminSourceSuggestionsPage />} />
          <Route path="/admin/providers" element={<AdminProvidersPage />} />
          <Route path="/admin/quota" element={<AdminQuotaPage />} />
          <Route path="/admin/funnel" element={<AdminFunnelPage />} />
          <Route path="/admin/corrections" element={<AdminCorrectionsPage />} />
          <Route path="/admin/work-person-ai" element={<AdminWorkPersonAiPage />} />
        </Route>
      </Routes>
    </Suspense>
  );
}
