import { useState } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";

import { Sidebar } from "@/components/layout/Sidebar";
import { TopBar } from "@/components/layout/TopBar";
import { MobileSidebar } from "@/components/layout/MobileSidebar";
import { CommandPalette } from "@/components/layout/CommandPalette";
import { useBOSShortcuts } from "@/hooks/useKeyboardShortcut";
import { useUIStore } from "@/store/uiStore";
import { useTheme } from "@/providers/ThemeProvider";
import { cn } from "@/lib/utils";
import { pageTransition } from "@/lib/motion";

export function AppLayout() {
  const location = useLocation();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const collapsed = useUIStore((state) => state.sidebarCollapsed);
  const toggleSidebar = useUIStore((state) => state.toggleSidebar);
  const openCommandPalette = useUIStore((state) => state.openCommandPalette);
  const closeCommandPalette = useUIStore((state) => state.closeCommandPalette);
  const commandPaletteOpen = useUIStore((state) => state.commandPaletteOpen);
  const { toggleTheme } = useTheme();

  useBOSShortcuts({
    onSearch: () => {
      if (commandPaletteOpen) {
        closeCommandPalette();
      } else {
        openCommandPalette();
      }
    },
    onToggleSidebar: toggleSidebar,
    onToggleTheme: toggleTheme,
    onEscape: () => {
      if (commandPaletteOpen) closeCommandPalette();
      if (mobileMenuOpen) setMobileMenuOpen(false);
    },
  });

  return (
    <div className="premium-shell min-h-screen">
      <div className="pointer-events-none fixed inset-0 opacity-70">
        <div className="absolute left-[8%] top-0 h-72 w-72 rounded-full bg-brand-500/8 blur-3xl" />
        <div className="absolute right-[6%] top-20 h-80 w-80 rounded-full bg-sky-500/10 blur-3xl" />
      </div>

      <Sidebar />
      <MobileSidebar open={mobileMenuOpen} onClose={() => setMobileMenuOpen(false)} />
      <CommandPalette />

      <div
        className={cn(
          "relative min-h-screen transition-all duration-200",
          collapsed ? "lg:ml-20" : "lg:ml-[17.5rem]",
        )}
      >
        <TopBar onMobileMenuOpen={() => setMobileMenuOpen(true)} />

        <main className="px-4 py-6 lg:px-8 lg:py-8">
          <div className="mx-auto max-w-[90rem]">
            <AnimatePresence mode="wait">
              <motion.div key={location.pathname} {...pageTransition}>
                <Outlet />
              </motion.div>
            </AnimatePresence>
          </div>
        </main>

        <footer className="border-t border-white/8 px-4 py-4 lg:px-8">
          <div className="mx-auto flex max-w-[90rem] items-center justify-between gap-3 text-xs text-surface-500">
            <p>BOS Pipeline v9.0</p>
            <p>Audit visibility, release discipline, premium operator UX.</p>
          </div>
        </footer>
      </div>
    </div>
  );
}
