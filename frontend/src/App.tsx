import {
  Navigate,
  Route,
  BrowserRouter as Router,
  Routes,
} from "react-router-dom";
import { AppLayout } from "./components/layout/AppLayout";
import { isAuthenticated } from "./lib/auth";
import { Escalations } from "./pages/Escalations";
import { Login } from "./pages/Login";
import { Overview } from "./pages/Overview";
import { PatientDetail } from "./pages/PatientDetail";
import { Patients } from "./pages/Patients";
import { Settings } from "./pages/Settings";

function RequireAuth({ children }: { children: React.ReactNode }) {
  if (!isAuthenticated()) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <Router>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          element={
            <RequireAuth>
              <AppLayout />
            </RequireAuth>
          }
        >
          <Route path="/" element={<Overview />} />
          <Route path="/patients" element={<Patients />} />
          <Route path="/patients/:id" element={<PatientDetail />} />
          <Route path="/escalations" element={<Escalations />} />
          <Route path="/settings" element={<Settings />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Router>
  );
}
