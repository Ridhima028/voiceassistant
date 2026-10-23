import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { EMAIL_KEY, TOKEN_KEY, api, setUnauthorizedHandler, storage } from "../services/api";

interface AuthState {
  token: string | null;
  /** There is no /me endpoint, so this is the email the user logged in with. */
  email: string | null;
  login: (email: string, password: string) => Promise<void>;
  signup: (username: string, email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() => storage.get(TOKEN_KEY));
  const [email, setEmail] = useState<string | null>(() => storage.get(EMAIL_KEY));

  const logout = useCallback(() => {
    storage.remove(TOKEN_KEY);
    storage.remove(EMAIL_KEY);
    setToken(null);
    setEmail(null);
  }, []);

  const login = useCallback(async (loginEmail: string, password: string) => {
    const { access_token } = await api.login(loginEmail, password);
    storage.set(TOKEN_KEY, access_token);
    storage.set(EMAIL_KEY, loginEmail);
    setToken(access_token);
    setEmail(loginEmail);
  }, []);

  const signup = useCallback(
    async (username: string, signupEmail: string, password: string) => {
      await api.signup(username, signupEmail, password);
      await login(signupEmail, password);
    },
    [login],
  );

  // Expired or invalid token anywhere in the app -> back to the login page.
  useEffect(() => {
    setUnauthorizedHandler(logout);
    return () => setUnauthorizedHandler(null);
  }, [logout]);

  const value = useMemo(
    () => ({ token, email, login, signup, logout }),
    [token, email, login, signup, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
