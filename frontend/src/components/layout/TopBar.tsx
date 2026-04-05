import { Bell, Command, Menu, Moon, Search, Sun } from "lucide-react";
import { useLocation } from "react-router-dom";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { useTheme } from "@/providers/ThemeProvider";
import { useUIStore } from "@/store/uiStore";
import { cn } from "@/lib/utils";
import { findNavItem } from "@/lib/navigation";

interface TopBarProps {
  onMobileMenuOpen: () => void;
}

export function TopBar({ onMobileMenuOpen }: TopBarProps) {
  const location = useLocation();
  const activeNav = findNavItem(location.pathname);
  const { resolvedTheme, toggleTheme } = useTheme();
  const openCommandPalette = useUIStore((state) => state.openCommandPalette);
  const unreadCount = useUIStore((state) => state.unreadCount);

  return (
    <header
      className={cn(
        "sticky top-0 z-30 border-b border-white/8 bg-surface-950/85 px-4 py-4 backdrop-blur-xl lg:px-8",
      )}
    >
      <div className="mx-auto flex max-w-[90rem] items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-3">
          <Button
            variant="ghost"
            size="icon"
            className="lg:hidden"
            onClick={onMobileMenuOpen}
            aria-label="Open menu"
          >
            <Menu className="h-5 w-5" />
          </Button>

          <div className="min-w-0">
            <div className="flex items-center gap-2">
              {activeNav ? (
                <Badge variant="info" className="hidden sm:inline-flex">
                  {activeNav.section}
                </Badge>
              ) : null}
              <p className="truncate text-sm font-semibold text-white">
                {activeNav?.label ?? "BOS Control"}
              </p>
            </div>
            <p className="mt-1 hidden truncate text-xs text-surface-400 sm:block">
              {activeNav?.description ?? "Protocol-first operations and evidence visibility."}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={openCommandPalette}
            className={cn(
              "hidden items-center gap-2 rounded-2xl border border-white/10 bg-white/6 px-3.5 py-2 text-sm text-surface-300 transition-colors",
              "hover:bg-white/10 hover:text-white sm:flex",
            )}
          >
            <Search className="h-4 w-4" />
            <span>Search command center</span>
            <kbd className="ml-4 inline-flex items-center gap-1 rounded-lg border border-white/10 bg-white/6 px-1.5 py-0.5 text-[10px] text-surface-400">
              <Command className="h-3 w-3" />K
            </kbd>
          </button>

          <Badge variant="success" dot className="hidden md:inline-flex">
            Audit-ready
          </Badge>

          <Button variant="ghost" size="icon" onClick={toggleTheme} aria-label="Toggle theme">
            {resolvedTheme === "dark" ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
          </Button>

          <div className="relative">
            <Button variant="ghost" size="icon" aria-label="Notifications">
              <Bell className="h-5 w-5" />
            </Button>
            {unreadCount > 0 ? (
              <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-[1rem] items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-bold text-white">
                {unreadCount > 99 ? "99+" : unreadCount}
              </span>
            ) : null}
          </div>
        </div>
      </div>
    </header>
  );
}
