import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./context/AuthContext";
import AppLayout from "./layouts/AppLayout";
import AuthPage from "./pages/AuthPage";
import Dashboard from "./pages/Dashboard";
import LecturePage from "./pages/LecturePage";

export default function App() {
  const { token } = useAuth();

  if (!token) {
    return (
      <Routes>
        <Route path="/login" element={<AuthPage mode="login" />} />
        <Route path="/signup" element={<AuthPage mode="signup" />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    );
  }

  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/lectures/:id" element={<LecturePage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
