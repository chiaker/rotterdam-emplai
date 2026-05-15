import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useAuthStore } from './store/auth';
import { Layout } from './components/Layout';
import { ProtectedRoute } from './components/ProtectedRoute';
import { Login } from './pages/Login';
import { Register } from './pages/Register';
import { Vacancies } from './pages/Vacancies';
import { VacancyDetail } from './pages/VacancyDetail';
import { Resumes } from './pages/Resumes';
import { ResumeDetail } from './pages/ResumeDetail';
import { Matches } from './pages/Matches';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

function AppRoutes() {
  const { isAuthenticated } = useAuthStore();

  return (
    <Routes>
      {/* Public routes */}
      <Route
        path="/login"
        element={isAuthenticated ? <Navigate to="/vacancies" replace /> : <Login />}
      />
      <Route
        path="/register"
        element={isAuthenticated ? <Navigate to="/vacancies" replace /> : <Register />}
      />

      {/* Protected routes */}
      <Route
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route path="/" element={<Navigate to="/vacancies" replace />} />
        <Route path="/vacancies" element={<Vacancies />} />
        <Route path="/vacancies/:id" element={<VacancyDetail />} />
        <Route path="/resumes" element={<Resumes />} />
        <Route path="/resumes/:id" element={<ResumeDetail />} />
        <Route path="/matches" element={<Matches />} />
      </Route>

      {/* 404 */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </QueryClientProvider>
  );
}
