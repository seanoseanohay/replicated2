import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { authApi } from "../api/client";

export interface AuthUser {
  id: string;
  email: string;
  role: "analyst" | "manager" | "admin";
  tenant_id: string;
}

interface AuthContextType {
  user: AuthUser | null;
  token: string | null;
  login(email: string, password: string): Promise<void>;
  register(email: string, password: string, fullName?: string): Promise<void>;
  logout(): void;
  isManager: boolean;
  isAdmin: boolean;
  isLoading: boolean;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [token, setToken] = useState<string | null>(
    localStorage.getItem("access_token")
  );
  const [isLoading, setIsLoading] = useState(true);

  // On mount, try to restore session from stored token
  useEffect(() => {
    const storedToken = localStorage.getItem("access_token");
    if (!storedToken) {
      setIsLoading(false);
      return;
    }
    authApi
      .me()
      .then((u) => {
        setUser({
          id: u.id,
          email: u.email,
          role: u.role as AuthUser["role"],
          tenant_id: u.tenant_id,
        });
        setToken(storedToken);
      })
      .catch(() => {
        // Token is invalid or expired — clear it
        localStorage.removeItem("access_token");
        localStorage.removeItem("refresh_token");
        setToken(null);
        setUser(null);
      })
      .finally(() => setIsLoading(false));
  }, []);

  const _applyTokenResponse = useCallback(
    (data: { access_token: string; refresh_token: string; role: string; tenant_id: string; email?: string; id?: string }) => {
      localStorage.setItem("access_token", data.access_token);
      localStorage.setItem("refresh_token", data.refresh_token);
      setToken(data.access_token);
      // Fetch full user info
      authApi.me().then((u) => {
        setUser({
          id: u.id,
          email: u.email,
          role: u.role as AuthUser["role"],
          tenant_id: u.tenant_id,
        });
      });
    },
    []
  );

  const login = useCallback(
    async (email: string, password: string) => {
      const data = await authApi.login(email, password);
      _applyTokenResponse(data);
    },
    [_applyTokenResponse]
  );

  const register = useCallback(
    async (email: string, password: string, fullName?: string) => {
      const data = await authApi.register(email, password, fullName);
      _applyTokenResponse(data);
    },
    [_applyTokenResponse]
  );

  const logout = useCallback(() => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    setToken(null);
    setUser(null);
  }, []);

  const isManager =
    user?.role === "manager" || user?.role === "admin" || false;
  const isAdmin = user?.role === "admin" || false;

  return (
    <AuthContext.Provider
      value={{ user, token, login, register, logout, isManager, isAdmin, isLoading }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextType {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}
