/**
 * BOS Pipeline v9.0 UI store.
 *
 * Zustand store for sidebar, command palette, and notification state.
 */

import { create } from "zustand";
import { persist } from "zustand/middleware";

interface UIState {
  // Locale
  locale: "en-US" | "zh-CN";
  setLocale: (locale: "en-US" | "zh-CN") => void;
  toggleLocale: () => void;

  // Sidebar
  sidebarCollapsed: boolean;
  toggleSidebar: () => void;
  setSidebarCollapsed: (collapsed: boolean) => void;

  // Command palette
  commandPaletteOpen: boolean;
  openCommandPalette: () => void;
  closeCommandPalette: () => void;
  toggleCommandPalette: () => void;

  // Notifications
  unreadCount: number;
  setUnreadCount: (count: number) => void;
  incrementUnread: () => void;
  clearUnread: () => void;

  // Login transition
  loginTransitionActive: boolean;
  setLoginTransitionActive: (active: boolean) => void;

  // Assistant arrival effect
  assistantArrivalBurst:
    | {
        token: number;
        source: "login";
        amplitude: number;
        createdAt: number;
      }
    | null;
  triggerAssistantArrivalBurst: (amplitude?: number) => void;
  clearAssistantArrivalBurst: () => void;

  // Login gesture preferences
  loginCameraAutoStart: boolean;
  setLoginCameraAutoStart: (enabled: boolean) => void;
  loginGestureGuideCollapsed: boolean;
  toggleLoginGestureGuideCollapsed: () => void;
}

export const useUIStore = create<UIState>()(
  persist(
    (set) => ({
      // Locale
      locale: "en-US",
      setLocale: (locale) => set({ locale }),
      toggleLocale: () =>
        set((s) => ({ locale: s.locale === "zh-CN" ? "en-US" : "zh-CN" })),

      // Sidebar
      sidebarCollapsed: false,
      toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
      setSidebarCollapsed: (collapsed) => set({ sidebarCollapsed: collapsed }),

      // Command palette
      commandPaletteOpen: false,
      openCommandPalette: () => set({ commandPaletteOpen: true }),
      closeCommandPalette: () => set({ commandPaletteOpen: false }),
      toggleCommandPalette: () =>
        set((s) => ({ commandPaletteOpen: !s.commandPaletteOpen })),

      // Notifications
      unreadCount: 0,
      setUnreadCount: (count) => set({ unreadCount: count }),
      incrementUnread: () => set((s) => ({ unreadCount: s.unreadCount + 1 })),
      clearUnread: () => set({ unreadCount: 0 }),

      // Login transition
      loginTransitionActive: false,
      setLoginTransitionActive: (active) => set({ loginTransitionActive: active }),

      // Assistant arrival effect
      assistantArrivalBurst: null,
      triggerAssistantArrivalBurst: (amplitude = 1) =>
        set({
          assistantArrivalBurst: {
            token: Date.now(),
            source: "login",
            amplitude,
            createdAt: Date.now(),
          },
        }),
      clearAssistantArrivalBurst: () => set({ assistantArrivalBurst: null }),

      // Login gesture preferences
      loginCameraAutoStart: true,
      setLoginCameraAutoStart: (enabled) => set({ loginCameraAutoStart: enabled }),
      loginGestureGuideCollapsed: false,
      toggleLoginGestureGuideCollapsed: () =>
        set((state) => ({
          loginGestureGuideCollapsed: !state.loginGestureGuideCollapsed,
        })),
    }),
    {
      name: "bos-ui-store",
      partialize: (state) => ({
        locale: state.locale,
        sidebarCollapsed: state.sidebarCollapsed,
        loginCameraAutoStart: state.loginCameraAutoStart,
        loginGestureGuideCollapsed: state.loginGestureGuideCollapsed,
      }),
    },
  ),
);
