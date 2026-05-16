/**
 * BOS Pipeline v9.0 auth store.
 *
 * Manages authentication state: tokens, user profile, and login/logout actions.
 */

import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

import client from "@/api/client";

export interface AuthUser {
  id: number;
  username: string;
  full_name: string;
  email: string | null;
  role: string;
  is_active: boolean;
}

interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

interface LoginPayload {
  username: string;
  password: string;
}

interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  user: AuthUser | null;
  isLoading: boolean;
  error: string | null;
  isAuthenticated: boolean;
  login: (payload: LoginPayload) => Promise<void>;
  logout: () => void;
  fetchProfile: () => Promise<void>;
  setUser: (user: AuthUser | null) => void;
  setTokens: (access: string, refresh: string) => void;
  clearError: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      // Initial state
      accessToken: null,
      refreshToken: null,
      user: null,
      isLoading: false,
      error: null,
      isAuthenticated: false,

      // Login
      login: async (payload) => {
        set({ isLoading: true, error: null });
        try {
          const { data } = await client.post<TokenPair>("/auth/login", payload);

          set({
            accessToken: data.access_token,
            refreshToken: data.refresh_token,
            isAuthenticated: true,
            error: null,
          });

          await get().fetchProfile();
        } catch (err: unknown) {
          const message =
            (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
            "Login failed";

          set({
            accessToken: null,
            refreshToken: null,
            user: null,
            isAuthenticated: false,
            error: message,
          });
          throw new Error(message);
        } finally {
          set({ isLoading: false });
        }
      },

      // Logout
      logout: () => {
        set({
          accessToken: null,
          refreshToken: null,
          user: null,
          isAuthenticated: false,
          error: null,
        });
      },

      // Fetch profile
      fetchProfile: async () => {
        const token = get().accessToken;
        if (!token) return;

        set({ isLoading: true });
        try {
          const { data } = await client.get<AuthUser>("/auth/me");
          set({ user: data, isAuthenticated: true });
        } catch {
          get().logout();
        } finally {
          set({ isLoading: false });
        }
      },

      setUser: (user) => {
        set({
          user,
          isAuthenticated: !!user || !!get().accessToken,
        });
      },

      // Set tokens
      setTokens: (access, refresh) => {
        set({
          accessToken: access,
          refreshToken: refresh,
          isAuthenticated: true,
        });
      },

      // Clear error
      clearError: () => set({ error: null }),
    }),
    {
      name: "bos-auth",
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
      }),
    },
  ),
);
