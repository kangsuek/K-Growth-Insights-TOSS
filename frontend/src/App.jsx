import { Suspense, lazy } from "react";
import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { SettingsProvider } from "./contexts/SettingsContext";
import { ToastProvider } from "./contexts/ToastContext";
import ErrorBoundary from "./components/common/ErrorBoundary";
import ToastContainer from "./components/common/ToastContainer";
import Header from "./components/layout/Header";
import Footer from "./components/layout/Footer";
import LoadingIndicator from "./components/common/LoadingIndicator";
import { CACHE_STALE_TIME_FAST, CACHE_GC_TIME } from "./constants";

const Dashboard = lazy(() => import("./pages/Dashboard.jsx"));
const Screening = lazy(() => import("./pages/Screening.jsx"));
const Comparison = lazy(() => import("./pages/Comparison.jsx"));
const Simulation = lazy(() => import("./pages/Simulation.jsx"));
const Portfolio = lazy(() => import("./pages/Portfolio.jsx"));
const Alerts = lazy(() => import("./pages/Alerts.jsx"));
const Settings = lazy(() => import("./pages/Settings.jsx"));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: CACHE_STALE_TIME_FAST,
      gcTime: CACHE_GC_TIME,
    },
  },
});

export default function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <SettingsProvider>
          <ToastProvider>
            <Router>
              <ErrorBoundary>
                <div className="flex flex-col min-h-screen bg-gray-50 dark:bg-gray-900 transition-colors">
                  <Header />
                  <main className="flex-grow container mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-8">
                    <ErrorBoundary>
                      <Suspense
                        fallback={
                          <div className="flex justify-center items-center h-64">
                            <LoadingIndicator size="lg" text="페이지 로딩 중..." />
                          </div>
                        }
                      >
                        <Routes>
                          <Route path="/" element={<Dashboard />} />
                          <Route path="/scanner" element={<Screening />} />
                          <Route path="/compare" element={<Comparison />} />
                          <Route path="/simulation" element={<Simulation />} />
                          <Route path="/portfolio" element={<Portfolio />} />
                          <Route path="/alerts" element={<Alerts />} />
                          <Route path="/settings" element={<Settings />} />
                        </Routes>
                      </Suspense>
                    </ErrorBoundary>
                  </main>
                  <Footer />
                </div>
              </ErrorBoundary>
              <ToastContainer />
            </Router>
          </ToastProvider>
        </SettingsProvider>
      </QueryClientProvider>
    </ErrorBoundary>
  );
}
