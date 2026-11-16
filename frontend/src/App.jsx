import { BrowserRouter, Link, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import { Empty } from "./components/ui";
import { AuthProvider, CompareProvider, SavedProvider, useAuth } from "./context";
import AdminUsersPage from "./pages/AdminUsersPage";
import AskPage from "./pages/AskPage";
import AuthPage from "./pages/AuthPage";
import ComparePage from "./pages/ComparePage";
import DeadlinesPage from "./pages/DeadlinesPage";
import DiscoverPage from "./pages/DiscoverPage";
import FacultyPage from "./pages/FacultyPage";
import FundingPage from "./pages/FundingPage";
import ProfilePage from "./pages/ProfilePage";
import ProgramDetailPage from "./pages/ProgramDetailPage";
import RecommendationsPage from "./pages/RecommendationsPage";
import SavedPage from "./pages/SavedPage";

function NotFound() {
  return (
    <div className="page">
      <Empty title="Page not found" action={<Link className="primary" to="/">Go to Discover</Link>}>
        The page you are looking for does not exist.
      </Empty>
    </div>
  );
}

export function AppRoutes() {
  const { user } = useAuth();
  if (!user) return <AuthPage />;
  return (
    <SavedProvider key={user.id}>
      <CompareProvider>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<DiscoverPage />} />
            <Route path="programs/:id" element={<ProgramDetailPage />} />
            <Route path="recommendations" element={<RecommendationsPage />} />
            <Route path="faculty" element={<FacultyPage />} />
            <Route path="funding" element={<FundingPage />} />
            <Route path="saved" element={<SavedPage />} />
            <Route path="deadlines" element={<DeadlinesPage />} />
            <Route path="compare" element={<ComparePage />} />
            <Route path="ask" element={<AskPage />} />
            <Route path="ask/:conversationId" element={<AskPage />} />
            <Route path="profile" element={<ProfilePage />} />
            <Route path="admin/users" element={<AdminUsersPage />} />
            <Route path="*" element={<NotFound />} />
          </Route>
        </Routes>
      </CompareProvider>
    </SavedProvider>
  );
}

export default function App() {
  return (
    <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  );
}
