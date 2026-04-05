import { NavLink, useNavigate } from "react-router-dom";
import { ChevronLeft, ChevronRight, LogOut, Sparkles } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { useAuthStore } from "@/store/authStore";
import { useUIStore } from "@/store/uiStore";
import { hasMinimumRole } from "@/types/auth";
import { cn } from "@/lib/utils";
import { NAV_ITEMS } from "@/lib/navigation";

export function Sidebar() {
  const navigate = useNavigate();
  const user = useAuthStore((state) => state.user);
  const logout = useAuthStore((state) => state.logout);
  const collapsed = useUIStore((state) => state.sidebarCollapsed);
  const toggleSidebar = useUIStore((state) => state.toggleSidebar);

  const visibleItems = NAV_ITEMS.filter(
    (item) => !item.minRole || hasMinimumRole(user?.role ?? "viewer", item.minRole),
  );

  const sections = [...new Set(visibleItems.map((item) => item.section))];

  return (
    <aside
      className={cn(
        "premium-shell fixed inset-y-0 left-0 z-40 hidden border-r border-white/10 lg:flex lg:flex-col",
        "transition-all duration-200",
        collapsed ? "w-20" : "w-[17.5rem]",
      )}
    >
      <div
        className={cn(
          "flex h-20 items-center border-b border-white/8 px-5",
          collapsed ? "justify-center" : "justify-between",
        )}
      >
        <div className={cn("flex items-center gap-3", collapsed && "justify-center")}>
          <div className="flex h-11 w-11 items-center justify-center rounded-2xl border border-brand-400/20 bg-brand-500/15 text-brand-200 shadow-glow">
            <Sparkles className="h-5 w-5" />
          </div>
          {!collapsed ? (
            <div className="space-y-1">
              <p className="font-display text-sm font-semibold tracking-[0.22em] text-white">
                BOS CONTROL
              </p>
              <p className="text-xs text-surface-400">Protocol-first operator console</p>
            </div>
          ) : null}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-3 py-5 scrollbar-hide">
        <div className="space-y-5">
          {sections.map((section) => (
            <div key={section} className="space-y-2">
              {!collapsed ? (
                <p className="px-3 text-[0.68rem] font-semibold uppercase tracking-[0.24em] text-surface-500">
                  {section}
                </p>
              ) : null}

              <ul className="space-y-1">
                {visibleItems
                  .filter((item) => item.section === section)
                  .map((item) => (
                    <li key={item.to}>
                      <NavLink
                        to={item.to}
                        title={collapsed ? item.label : undefined}
                        className={({ isActive }) =>
                          cn(
                            "group flex items-center gap-3 rounded-2xl border px-3 py-3 text-sm transition-all duration-150",
                            isActive
                              ? "border-brand-400/20 bg-brand-500/15 text-white shadow-glow"
                              : "border-transparent text-surface-400 hover:border-white/8 hover:bg-white/6 hover:text-white",
                            collapsed && "justify-center px-2",
                          )
                        }
                      >
                        <span className="flex-shrink-0">{item.icon}</span>
                        {!collapsed ? (
                          <span className="min-w-0">
                            <span className="block truncate font-medium">{item.shortLabel}</span>
                            <span className="mt-0.5 block truncate text-xs text-surface-500 group-hover:text-surface-400">
                              {item.description}
                            </span>
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

      <div className="border-t border-white/8 p-3">
        {!collapsed ? (
          <div className="premium-panel mb-3 p-3">
            <div className="flex items-center justify-between gap-2">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.24em] text-surface-500">
                  Runtime
                </p>
                <p className="mt-1 text-sm text-white">BOS v9.0</p>
              </div>
              <Badge variant="success" dot>
                Stable
              </Badge>
            </div>
            {user ? (
              <div className="mt-4 rounded-2xl border border-white/8 bg-white/5 px-3 py-2">
                <p className="truncate text-sm font-medium text-white">{user.full_name}</p>
                <p className="truncate text-xs text-surface-400">{user.role}</p>
              </div>
            ) : null}
          </div>
        ) : null}

        <button
          onClick={() => {
            logout();
            navigate("/login");
          }}
          className={cn(
            "flex w-full items-center gap-3 rounded-2xl px-3 py-3 text-sm font-medium text-surface-400 transition-colors hover:bg-red-500/10 hover:text-red-200",
            collapsed && "justify-center px-2",
          )}
          title={collapsed ? "Logout" : undefined}
        >
          <LogOut className="h-5 w-5 flex-shrink-0" />
          {!collapsed ? <span>Logout</span> : null}
        </button>

        <button
          onClick={toggleSidebar}
          className={cn(
            "mt-1 flex w-full items-center gap-3 rounded-2xl px-3 py-3 text-sm text-surface-500 transition-colors hover:bg-white/6 hover:text-white",
            collapsed && "justify-center px-2",
          )}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
          {!collapsed ? <span>Collapse</span> : null}
        </button>
      </div>
    </aside>
  );
}
