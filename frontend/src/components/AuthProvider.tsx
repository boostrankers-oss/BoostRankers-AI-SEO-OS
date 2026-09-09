import {
  createContext,
  useContext,
  useEffect,
  useState,
  ReactNode,
} from "react";
import { api } from "@/lib/api";

export type UserRole =
  | "super_admin"
  | "agency_admin"
  | "manager"
  | "seo_specialist"
  | "client";

export interface User {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  role: UserRole;
  company_id: string | null;
  is_verified: boolean;
}

interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type?: string;
}

interface AuthResponse {
  user: User;
  tokens: AuthTokens;
}

interface AuthContextType {
  user: User | null;
  login: (email: string, password: string) => Promise<void>;
  signup: (data: {
    email: string;
    password: string;
    confirm_password: string;
    first_name: string;
    last_name: string;
    company_name?: string;
  }) => Promise<void>;
  logout: () => Promise<void>;
  loading: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

function saveSession(user: User, tokens: AuthTokens): void {
  localStorage.setItem("access_token", tokens.access_token);
  localStorage.setItem("refresh_token", tokens.refresh_token);
  localStorage.setItem("boost_user", JSON.stringify(user));
}

function clearSession(): void {
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
  localStorage.removeItem("boost_user");
}

export function AuthProvider({
  children,
}: {
  children: ReactNode;
}) {
  const [user, setUser] = useState<User | null>(() => {
    try {
      const stored = localStorage.getItem("boost_user");
      return stored ? (JSON.parse(stored) as User) : null;
    } catch {
      localStorage.removeItem("boost_user");
      return null;
    }
  });

  // Cached session hydration is synchronous. Do not block the auth UI
  // while the background /api/auth/me validation is running.
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let mounted = true;

    const restoreSession = async () => {
      const accessToken = localStorage.getItem("access_token");
      const refreshToken = localStorage.getItem("refresh_token");

      if (!accessToken || !refreshToken) {
        if (mounted) {
          setUser(null);
          setLoading(false);
        }
        return;
      }

      try {
        const currentUser = await api.get<User>("/api/auth/me");

        if (mounted) {
          setUser(currentUser);
          localStorage.setItem(
            "boost_user",
            JSON.stringify(currentUser)
          );
        }
      } catch (error: any) {
        const status = error?.status;

        console.warn("Session restoration request failed:", error);

        // Keep the locally restored session during temporary network/server
        // failures. The API client clears it only when the refresh token is
        // genuinely rejected/expired.
        if (status === 401 || status === 403) {
          clearSession();
          if (mounted) {
            setUser(null);
          }
        }
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    };

    restoreSession();

    const handleAuthExpired = () => {
      if (!mounted) return;

      clearSession();
      setUser(null);
      setLoading(false);
    };

    window.addEventListener("auth:expired", handleAuthExpired);

    return () => {
      mounted = false;
      window.removeEventListener(
        "auth:expired",
        handleAuthExpired
      );
    };
  }, []);

  const login = async (
    email: string,
    password: string
  ): Promise<void> => {
    // `loading` is reserved for initial session restoration.
    // Do not toggle it during login, otherwise App.tsx can show
    // "Restoring session..." while the user is actively logging in.
    try {
      const response = await api.post<AuthResponse>(
        "/api/auth/login",
        {
          email,
          password,
        },
        {
          auth: false,
        }
      );

      const { user: loggedInUser, tokens } = response;

      saveSession(loggedInUser, tokens);
      setUser(loggedInUser);
    } catch (error) {
      console.error("Login failed:", error);
      throw error;
    }
  };

  const signup = async (data: {
    email: string;
    password: string;
    confirm_password: string;
    first_name: string;
    last_name: string;
    company_name?: string;
  }): Promise<void> => {
    // `loading` is reserved for initial session restoration.
    // Do not toggle it during signup for the same reason as login.
    try {
      const payload = {
        ...data,
        full_name: `${data.first_name} ${data.last_name}`.trim(),
      };

      /*
       * The supplied backend auth router exposes /register,
       * not /signup.
       */
      const response = await api.post<AuthResponse>(
        "/api/auth/register",
        payload,
        {
          auth: false,
        }
      );

      const { user: registeredUser, tokens } = response;

      saveSession(registeredUser, tokens);
      setUser(registeredUser);
    } catch (error) {
      console.error("Signup failed:", error);
      throw error;
    }
  };

  const logout = async (): Promise<void> => {
    const refreshToken =
      localStorage.getItem("refresh_token");

    try {
      if (refreshToken) {
        await api.post(
          "/api/auth/logout",
          {
            refresh_token: refreshToken,
          },
          {
            auth: false,
            skipRefresh: true,
          }
        );
      }
    } catch (error) {
      /*
       * Logout must still clear the local session when the
       * network/server is unavailable.
       */
      console.warn("Server logout failed:", error);
    } finally {
      clearSession();
      setUser(null);
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        login,
        signup,
        logout,
        loading,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error(
      "useAuth must be used within AuthProvider"
    );
  }

  return context;
}
