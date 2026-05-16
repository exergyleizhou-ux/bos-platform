import { NavLink, useLocation, useNavigate } from "react-router-dom";
import { ChevronLeft, ChevronRight, LogOut, Sparkles } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { SurfaceTile, surfaceActionButtonClasses, surfaceTileButtonClasses } from "@/components/ui/SurfaceTile";
import { useAuthStore } from "@/store/authStore";
import { useUIStore } from "@/store/uiStore";
import { hasMinimumRole } from "@/types/auth";
import { translateText } from "@/lib/i18n";
import { cn } from "@/lib/utils";
import { NAV_ITEMS } from "@/lib/navigation";

export function Sidebar() {
  const location = useLocation();
  const navigate = useNavigate();
  const user = useAuthStore((state) => state.user);
  const logout = useAuthStore((state) => state.logout);
  const collapsed = useUIStore((state) => state.sidebarCollapsed);
  const toggleSidebar = useUIStore((state) => state.toggleSidebar);
  const isCodeRoute = location.pathname.startsWith("/code");
  const isAssistantRoute = location.pathname.startsWith("/bos");
  const effectiveCollapsed = collapsed || isCodeRoute;

  const visibleItems = NAV_ITEMS.filter(
    (item) => !item.minRole || hasMinimumRole(user?.role ?? "viewer", item.minRole),
  );

  const sections = [...new Set(visibleItems.map((item) => item.section))];

  return (
    <aside
      className={cn(
        "premium-shell fixed inset-y-0 left-0 z-40 hidden border-r border-white/10 lg:flex lg:flex-col",
        "transition-all duration-200",
        effectiveCollapsed ? "w-20" : "w-[17.5rem]",
        isCodeRoute && "border-white/5 opacity-80",
      )}
    >
      <div
        className={cn(
          "flex h-20 items-center border-b border-white/8 px-5",
          effectiveCollapsed ? "justify-center" : "justify-between",
        )}
      >
        <div className={cn("flex items-center gap-3", effectiveCollapsed && "justify-center")}>
          <div className="flex h-11 w-11 items-center justify-center rounded-2xl border border-sky-300/20 bg-[linear-gradient(180deg,rgba(92,214,255,0.18),rgba(92,214,255,0.08))] text-sky-100 shadow-glow">
            <Sparkles className="h-5 w-5" />
          </div>
          {!effectiveCollapsed ? (
            <div className="space-y-1">
              <p className="font-display text-sm font-semibold tracking-[0.22em] text-white">
                {translateText("BOS")}
              </p>
              <p className="text-xs text-surface-400">{translateText("Biological Operating System")}</p>
            </div>
          ) : null}
        </div>
      </div>

      <div className={cn("flex-1 overflow-y-auto px-3 py-5 scrollbar-hide", isCodeRoute && "px-2 py-4")}>
        <div className="space-y-5">
          {sections.map((section) => (
            <div key={section} className="space-y-1.5">
              {!effectiveCollapsed ? (
                <p className={cn("px-3 text-[0.68rem] font-semibold uppercase tracking-[0.24em] text-surface-500", isAssistantRoute && "text-surface-600")}>
                  {translateText(section)}
                </p>
              ) : null}

              <ul className="space-y-1">
                  {visibleItems
                    .filter((item) => item.section === section)
                    .map((item) => (
                    <li key={item.to}>
                      <NavLink
                        to={item.to}
                        title={effectiveCollapsed ? translateText(item.label) : undefined}
                        className={({ isActive }) =>
                          cn(
                            "group flex items-center gap-3 rounded-2xl border px-3 py-3 text-sm transition-all duration-150",
                            surfaceTileButtonClasses(isActive),
                            isActive ? "text-white" : "text-surface-400 hover:text-white",
                            effectiveCollapsed && "justify-center px-2",
                            isCodeRoute && "rounded-[20px] py-3",
                          )
                        }
                      >
                        <span className="flex-shrink-0">{item.icon}</span>
                        {!effectiveCollapsed ? (
                          <span className="min-w-0">
                            <span className="block truncate font-medium">{translateText(item.shortLabel)}</span>
                            {!isAssistantRoute ? (
                              <span className="mt-0.5 block truncate text-xs text-surface-500 group-hover:text-surface-400">
                                {translateText(item.description)}
                              </span>
                            ) : null}
                          </span>
                        ) : null}
                      </NavLink>
                    </li>
                  ))}
              </ul>
            </div>
          ))}
        </div>
      </div>

      <div className={cn("border-t border-white/8 p-3", isCodeRoute && "border-white/5")}>
        {!effectiveCollapsed && !isCodeRoute && !isAssistantRoute ? (
          <SurfaceTile className="mb-3 p-3">
            <div className="flex items-center justify-between gap-2">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.24em] text-surface-500">
                  {translateText("Workspace")}
                </p>
                <p className="mt-1 text-sm text-white">{translateText("BOS v9.0")}</p>
              </div>
              <Badge variant="success" dot>
                Stable
              </Badge>
            </div>
            {user ? (
              <SurfaceTile className="mt-4 px-3 py-2">
                <p className="truncate text-sm font-medium text-white">{user.full_name}</p>
                <p className="truncate text-xs text-surface-400">{user.role}</p>
              </SurfaceTile>
            ) : null}
          </SurfaceTile>
        ) : null}

        <button
          onClick={() => {
            logout();
            navigate("/login");
          }}
          className={cn(
            "flex w-full items-center gap-3",
            surfaceActionButtonClasses("danger"),
            effectiveCollapsed && "justify-center px-2",
            isCodeRoute && "text-surface-500",
          )}
          title={effectiveCollapsed ? translateText("Logout") : undefined}
        >
          <LogOut className="h-5 w-5 flex-shrink-0" />
          {!effectiveCollapsed ? <span>{translateText("Logout")}</span> : null}
        </button>

        <button
          onClick={toggleSidebar}
          className={cn(
            "mt-1 flex w-full items-center gap-3",
            surfaceActionButtonClasses(),
            effectiveCollapsed && "justify-center px-2",
          )}
          aria-label={translateText(effectiveCollapsed ? "Expand sidebar" : "Collapse sidebar")}
        >
          {effectiveCollapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
          {!effectiveCollapsed && !isCodeRoute ? <span>{translateText("Collapse")}</span> : null}
        </button>
      </div>
    </aside>
  );
}
