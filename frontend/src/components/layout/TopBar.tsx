import { Bell, Command, Languages, Menu, Moon, Search, Sun } from "lucide-react";
import { useLocation } from "react-router-dom";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import {
  getLocaleToggleActionLabel,
  getLocaleToggleLabel,
  getThemeToggleLabel,
  translateText,
} from "@/lib/i18n";
import { findNavItem } from "@/lib/navigation";
import { cn } from "@/lib/utils";
import { useI18n } from "@/providers/I18nProvider";
import { useTheme } from "@/providers/ThemeProvider";
import { useUIStore } from "@/store/uiStore";

interface TopBarProps {
  onMobileMenuOpen: () => void;
}

export function TopBar({ onMobileMenuOpen }: TopBarProps) {
  const location = useLocation();
  const isCodeRoute = location.pathname.startsWith("/code");
  const isAssistantRoute = location.pathname.startsWith("/bos");
  const activeNav = findNavItem(location.pathname);
  const { resolvedTheme, toggleTheme } = useTheme();
  const { locale, toggleLocale } = useI18n();
  const openCommandPalette = useUIStore((state) => state.openCommandPalette);
  const unreadCount = useUIStore((state) => state.unreadCount);

  const localeToggleLabel = getLocaleToggleLabel(locale);
  const localeToggleAriaLabel = getLocaleToggleActionLabel(locale);
  const themeToggleLabel = getThemeToggleLabel(resolvedTheme, locale);
  const themeToggleAriaLabel = translateText("Toggle theme", locale);

  return (
    <header
      className={cn(
        "topbar-frost sticky top-0 z-30 px-4 py-3 lg:px-8",
        isCodeRoute && "py-3",
      )}
    >
      <div className="mx-auto flex max-w-[90rem] items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-3">
          <Button
            variant="ghost"
            size="icon"
            className="lg:hidden"
            onClick={onMobileMenuOpen}
            aria-label={translateText("Open menu")}
          >
            <Menu className="h-5 w-5" />
          </Button>

          <div className="min-w-0">
            <div className="flex items-center gap-2">
              {activeNav ? (
                <Badge
                  variant="neutral"
                  className={cn(
                    "hidden sm:inline-flex",
                    (isCodeRoute || isAssistantRoute) &&
                      "border-white/8 bg-white/4 text-surface-400",
                  )}
                >
                  {translateText(activeNav.section)}
                </Badge>
              ) : null}
              <p className="truncate text-sm font-semibold text-white">
                {activeNav ? translateText(activeNav.label) : translateText("BOS Assistant")}
              </p>
            </div>
            {!isAssistantRoute ? (
              <p className="mt-1 hidden truncate text-xs text-surface-400 sm:block">
                {isCodeRoute
                  ? translateText(
                      "A calmer engineering workspace with the control core just off to the side.",
                    )
                  : translateText(
                      activeNav?.description ??
                        "Protocol-first operations and evidence visibility.",
                    )}
              </p>
            ) : null}
          </div>
        </div>

        <div className="flex items-center gap-1.5">
          <Badge variant="info" className="hidden lg:inline-flex border border-sky-300/14 bg-sky-400/10 text-sky-100">
            {translateText("Operator runtime")}
          </Badge>
          {isCodeRoute || isAssistantRoute ? (
            <button
              onClick={openCommandPalette}
              className={cn(
                "cold-control-ghost hidden items-center gap-2 px-3.25 py-[0.45rem] sm:flex",
              )}
            >
              <Search className="h-3.5 w-3.5" />
              <span>{translateText(isCodeRoute ? "Search the thread" : "Search")}</span>
              <kbd className="cold-control-kbd ml-3 inline-flex items-center gap-1 px-1.5 py-0.5 text-[10px]">
                <Command className="h-3 w-3" />K
              </kbd>
            </button>
          ) : (
            <button
              onClick={openCommandPalette}
              className={cn(
                "cold-control-ghost hidden items-center gap-2 px-3.25 py-[0.45rem] sm:flex",
              )}
            >
              <Search className="h-3.5 w-3.5" />
              <span>{translateText("Search command center")}</span>
              <kbd className="cold-control-kbd ml-4 inline-flex items-center gap-1 px-1.5 py-0.5 text-[10px]">
                <Command className="h-3 w-3" />K
              </kbd>
            </button>
          )}

          {!isCodeRoute && !isAssistantRoute ? (
            <Badge variant="success" dot className="hidden md:inline-flex">
              {translateText("Audit-ready")}
            </Badge>
          ) : !isAssistantRoute ? (
            <Badge variant="neutral" className="hidden md:inline-flex">
              {translateText(isCodeRoute ? "Focus mode" : "Conversation mode")}
            </Badge>
          ) : null}

          <div
            data-i18n-skip
            className={cn(
              "cold-control-group hidden items-center gap-1.5 px-1.5 py-1 sm:flex",
              isAssistantRoute && "gap-1.5",
            )}
          >
            {!isAssistantRoute ? (
              <span className="cold-control-label px-2 text-[9px] font-semibold uppercase">
                {translateText("Language", locale)}
              </span>
            ) : null}
            <Button
              variant="secondary"
              size="sm"
              leftIcon={<Languages className="h-4 w-4" />}
              onClick={toggleLocale}
              aria-label={localeToggleAriaLabel}
              title={localeToggleAriaLabel}
              data-i18n-skip
              className={cn(
                "cold-control-pill h-9 px-3.5 text-sm font-medium",
                isAssistantRoute && "min-w-[7.25rem]",
              )}
            >
              {localeToggleLabel}
            </Button>
            <Button
              variant="secondary"
              size="sm"
              leftIcon={
                resolvedTheme === "dark" ? (
                  <Sun className="h-4 w-4" />
                ) : (
                  <Moon className="h-4 w-4" />
                )
              }
              onClick={toggleTheme}
              aria-label={themeToggleAriaLabel}
              title={themeToggleAriaLabel}
              data-i18n-skip
              className="cold-control-pill h-9 min-w-[6.25rem] px-3.5 text-sm font-medium"
            >
              {themeToggleLabel}
            </Button>
          </div>

          <Button
            variant="secondary"
            size="icon"
            className="cold-control-pill h-9 w-9 sm:hidden"
            onClick={toggleLocale}
            aria-label={localeToggleAriaLabel}
            title={localeToggleAriaLabel}
            data-i18n-skip
          >
            <Languages className="h-4 w-4" />
          </Button>

          {!isCodeRoute && !isAssistantRoute ? (
            <div className="relative">
              <Button variant="ghost" size="icon" aria-label={translateText("Notifications")}>
                <Bell className="h-5 w-5" />
              </Button>
              {unreadCount > 0 ? (
                <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-[1rem] items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-bold text-white">
                  {unreadCount > 99 ? "99+" : unreadCount}
                </span>
              ) : null}
            </div>
          ) : null}
        </div>
      </div>
    </header>
  );
}
