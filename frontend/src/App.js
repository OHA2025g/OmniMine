import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { Layout } from "./components/Layout";
import { LoginPage, RegisterPage } from "./pages/AuthPages";
import { DashboardPage } from "./pages/DashboardPage";
import { FeedbackPage } from "./pages/FeedbackPage";
import { CasesPage } from "./pages/CasesPage";
import { AnalyticsPage } from "./pages/AnalyticsPage";
import { AlertsPage } from "./pages/AlertsPage";
import { SurveysPage } from "./pages/SurveysPage";
import { SettingsPage } from "./pages/SettingsPage";
import { AgentsPage } from "./pages/AgentsPage";
import { AdminPage } from "./pages/AdminPage";
import { Toaster } from "sonner";

const ProtectedRoute = ({ children }) => {
  const { isAuthenticated, loading } = useAuth();
  
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <div className="text-center">
          <div className="w-12 h-12 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin mx-auto"></div>
          <p className="mt-4 text-muted-foreground">Loading...</p>
        </div>
      </div>
    );
  }
  
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  
  return children;
};

const PublicRoute = ({ children }) => {
  const { isAuthenticated, loading } = useAuth();
  
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <div className="w-12 h-12 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin"></div>
      </div>
    );
  }
  
  if (isAuthenticated) {
    return <Navigate to="/" replace />;
  }
  
  return children;
};

function AppRoutes() {
  return (
    <Routes>
      {/* Public routes */}
      <Route path="/login" element={
        <PublicRoute>
          <LoginPage />
        </PublicRoute>
      } />
      <Route path="/register" element={
        <PublicRoute>
          <RegisterPage />
        </PublicRoute>
      } />
      
      {/* Protected routes */}
      <Route path="/" element={
        <ProtectedRoute>
          <Layout />
        </ProtectedRoute>
      }>
        <Route index element={<DashboardPage />} />
        <Route path="feedback" element={<FeedbackPage />} />
        <Route path="cases" element={<CasesPage />} />
        <Route path="agents" element={<AgentsPage />} />
        <Route path="analytics" element={<AnalyticsPage />} />
        <Route path="alerts" element={<AlertsPage />} />
        <Route path="surveys" element={<SurveysPage />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="admin" element={<AdminPage />} />
      </Route>
      
      {/* Catch all */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Toaster position="top-right" richColors />
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
