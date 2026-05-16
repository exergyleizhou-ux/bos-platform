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
import { translateText } from "@/lib/i18n";
import { cn } from "@/lib/utils";
import { pageTransition } from "@/lib/motion";

export function AppLayout() {
  const location = useLocation();
  const isCodeRoute = location.pathname.startsWith("/code");
  const isAssistantRoute = location.pathname.startsWith("/bos");
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
          collapsed || isCodeRoute ? "lg:ml-20" : "lg:ml-[17.5rem]",
        )}
      >
        <TopBar onMobileMenuOpen={() => setMobileMenuOpen(true)} />

        <main className={cn("px-4 py-6 lg:px-8 lg:py-8", isAssistantRoute && "lg:py-7")}>
          <div className={cn("mx-auto", isCodeRoute ? "max-w-[100rem]" : isAssistantRoute ? "max-w-[96rem]" : "max-w-[90rem]")}>
            <AnimatePresence mode="wait">
              <motion.div key={location.pathname} {...pageTransition}>
                <Outlet />
              </motion.div>
            </AnimatePresence>
          </div>
        </main>

        <footer className={cn("border-t border-white/8 px-4 py-4 lg:px-8", (isCodeRoute || isAssistantRoute) && "opacity-50")}>
          <div className="mx-auto flex max-w-[90rem] items-center justify-between gap-3 text-xs text-surface-500">
            <p>{translateText("BOS v9.0")}</p>
            <p>{translateText("Conversation-first operating workspace with evidence and control surfaces nearby.")}</p>
          </div>
        </footer>
      </div>
    </div>
  );
}
