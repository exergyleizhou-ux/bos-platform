/**
 * BOS Pipeline v9.0 �� Auth Store (Zustand)
 *
 * Manages authentication state: tokens, user profile, login/logout.
 */

import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import client from "@/api/client";

// ���� Types ����
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
  // State
  accessToken: string | null;
  refreshToken: string | null;
  user: AuthUser | null;
  isLoading: boolean;
  error: string | null;

  // Computed
  isAuthenticated: boolean;

  // Actions
  login: (payload: LoginPayload) => Promise<void>;
  logout: () => void;
  fetchProfile: () => Promise<void>;
  setTokens: (access: string, refresh: string) => void;
  clearError: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      // ���� Initial State ����
      accessToken: null,
      refreshToken: null,
      user: null,
      isLoading: false,
      error: null,
      isAuthenticated: false,

      // ���� Login ����
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

          // Fetch profile
          await get().fetchProfile();
        } catch (err: unknown) {
          const message =
            (err as { response?: { data?: { detail?: string } } })?.response
              ?.data?.detail ?? "Login failed";
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

      // ���� Logout ����
      logout: () => {
        set({
          accessToken: null,
          refreshToken: null,
          user: null,
          isAuthenticated: false,
          error: null,
        });
      },

      // ���� Fetch Profile ����
      fetchProfile: async () => {
        const token = get().accessToken;
        if (!token) return;

        set({ isLoading: true });
        try {
          const { data } = await client.get<AuthUser>("/auth/me");
          set({ user: data, isAuthenticated: true });
        } catch {
          // Token may be expired �� logout
          get().logout();
        } finally {
          set({ isLoading: false });
        }
      },

      // ���� Set Tokens (for refresh) ����
      setTokens: (access, refresh) => {
        set({
          accessToken: access,
          refreshToken: refresh,
          isAuthenticated: true,
        });
      },

      // ���� Clear Error ����
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
