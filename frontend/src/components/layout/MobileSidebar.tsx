import { useEffect } from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import { LogOut, Sparkles, X } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { SurfaceTile, surfaceActionButtonClasses, surfaceTileButtonClasses } from "@/components/ui/SurfaceTile";
import { useAuthStore } from "@/store/authStore";
import { hasMinimumRole } from "@/types/auth";
import { translateText } from "@/lib/i18n";
import { cn } from "@/lib/utils";
import { NAV_ITEMS } from "@/lib/navigation";

interface MobileSidebarProps {
  open: boolean;
  onClose: () => void;
}

export function MobileSidebar({ open, onClose }: MobileSidebarProps) {
  const navigate = useNavigate();
  const location = useLocation();
  const user = useAuthStore((state) => state.user);
  const logout = useAuthStore((state) => state.logout);

  const visibleItems = NAV_ITEMS.filter(
    (item) => !item.minRole || hasMinimumRole(user?.role ?? "viewer", item.minRole),
  );

  const sections = [...new Set(visibleItems.map((item) => item.section))];

  useEffect(() => {
    if (open) onClose();
  }, [location.pathname, onClose, open]);

  useEffect(() => {
    document.body.style.overflow = open ? "hidden" : "";
    return () => {
      document.body.style.overflow = "";
    };
  }, [open]);

  return (
    <AnimatePresence>
      {open ? (
        <>
          <motion.div
            className="fixed inset-0 z-50 bg-black/55 backdrop-blur-sm lg:hidden"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.16 }}
            onClick={onClose}
          />

          <motion.aside
            className="premium-shell fixed inset-y-0 left-0 z-50 w-[19rem] border-r border-white/10 lg:hidden"
            initial={{ x: "-100%" }}
            animate={{ x: 0 }}
            exit={{ x: "-100%" }}
            transition={{ duration: 0.2, ease: [0.22, 1, 0.36, 1] }}
          >
            <div className="flex h-20 items-center justify-between border-b border-white/8 px-5">
              <div className="flex items-center gap-3">
                <div className="flex h-11 w-11 items-center justify-center rounded-2xl border border-brand-400/20 bg-brand-500/15 text-brand-200 shadow-glow">
                  <Sparkles className="h-5 w-5" />
                </div>
                <div>
                  <p className="font-display text-sm font-semibold tracking-[0.22em] text-white">
                    {translateText("BOS")}
                  </p>
                  <p className="text-xs text-surface-400">{translateText("Conversation-first workspace")}</p>
                </div>
              </div>

              <button
                onClick={onClose}
                className="rounded-2xl border border-white/10 bg-white/6 p-2 text-surface-300 transition-colors hover:text-white"
                aria-label={translateText("Close menu")}
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="overflow-y-auto px-3 py-5">
              <div className="space-y-5">
                {sections.map((section) => (
                  <div key={section} className="space-y-2">
                    <p className="px-3 text-[0.68rem] font-semibold uppercase tracking-[0.24em] text-surface-500">
                      {translateText(section)}
                    </p>
                    <ul className="space-y-1">
                      {visibleItems
                        .filter((item) => item.section === section)
                        .map((item) => (
                          <li key={item.to}>
                            <NavLink
                              to={item.to}
                              className={({ isActive }) =>
                                cn(
                                  "flex items-start gap-3 rounded-2xl border px-3 py-3 text-sm transition-all duration-150",
                                  surfaceTileButtonClasses(isActive),
                                  isActive ? "text-white" : "text-surface-400 hover:text-white",
                                )
                              }
                            >
                              <span className="mt-0.5 flex-shrink-0">{item.icon}</span>
                              <span className="min-w-0">
                                <span className="block font-medium">{translateText(item.label)}</span>
                                <span className="mt-0.5 block text-xs text-surface-500">
                                  {translateText(item.description)}
                                </span>
                              </span>
                            </NavLink>
                          </li>
                        ))}
                    </ul>
                  </div>
                ))}
              </div>
            </div>

            <div className="border-t border-white/8 p-4">
              <SurfaceTile className="p-3">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-white">{user?.full_name ?? translateText("Operator")}</p>
                    <p className="text-xs text-surface-400">{user?.role ?? "viewer"}</p>
                  </div>
                  <Badge variant="success" dot>
                    Stable
                  </Badge>
                </div>
              </SurfaceTile>

              <button
                onClick={() => {
                  logout();
                  onClose();
                  navigate("/login");
                }}
                className={cn("mt-3 flex w-full items-center gap-3", surfaceActionButtonClasses("danger"))}
              >
                <LogOut className="h-5 w-5" />
                <span>{translateText("Logout")}</span>
              </button>
            </div>
          </motion.aside>
        </>
      ) : null}
    </AnimatePresence>
  );
}
