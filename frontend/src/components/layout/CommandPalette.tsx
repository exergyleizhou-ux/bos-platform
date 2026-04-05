import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import { Plus, Search } from "lucide-react";

import { useAuthStore } from "@/store/authStore";
import { useUIStore } from "@/store/uiStore";
import { hasMinimumRole } from "@/types/auth";
import { cn } from "@/lib/utils";
import { NAV_ITEMS } from "@/lib/navigation";

interface CommandItem {
  id: string;
  label: string;
  description: string;
  icon: ReactNode;
  action: () => void;
  keywords: string[];
}

export function CommandPalette() {
  const navigate = useNavigate();
  const open = useUIStore((state) => state.commandPaletteOpen);
  const close = useUIStore((state) => state.closeCommandPalette);
  const user = useAuthStore((state) => state.user);

  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  const commands = useMemo<CommandItem[]>(
    () => [
      ...NAV_ITEMS.filter(
        (item) => !item.minRole || hasMinimumRole(user?.role ?? "viewer", item.minRole),
      ).map((item) => ({
        id: item.to,
        label: item.label,
        description: item.description,
        icon: item.icon,
        action: () => navigate(item.to),
        keywords: item.keywords ?? [],
      })),
      {
        id: "new-batch",
        label: "Create New Batch",
        description: "Open the batch intake form for a new command surface.",
        icon: <Plus className="h-4 w-4" />,
        action: () => navigate("/batches/new"),
        keywords: ["create", "batch", "new"],
      },
    ],
    [navigate, user?.role],
  );

  const filtered = useMemo(() => {
    if (!query.trim()) return commands;
    const value = query.toLowerCase();

    return commands.filter(
      (item) =>
        item.label.toLowerCase().includes(value) ||
        item.description.toLowerCase().includes(value) ||
        item.keywords.some((keyword) => keyword.toLowerCase().includes(value)),
    );
  }, [commands, query]);

  useEffect(() => {
    if (!open) return;
    setQuery("");
    setActiveIndex(0);
    window.setTimeout(() => inputRef.current?.focus(), 40);
  }, [open]);

  useEffect(() => {
    if (activeIndex >= filtered.length) {
      setActiveIndex(Math.max(0, filtered.length - 1));
    }
  }, [activeIndex, filtered.length]);

  useEffect(() => {
    if (!listRef.current) return;
    const activeItem = listRef.current.querySelector(`[data-index="${activeIndex}"]`);
    activeItem?.scrollIntoView({ block: "nearest" });
  }, [activeIndex]);

  const handleKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActiveIndex((current) => Math.min(current + 1, filtered.length - 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveIndex((current) => Math.max(current - 1, 0));
    } else if (event.key === "Enter" && filtered[activeIndex]) {
      event.preventDefault();
      filtered[activeIndex].action();
      close();
    } else if (event.key === "Escape") {
      close();
    }
  };

  return (
    <AnimatePresence>
      {open ? (
        <>
          <motion.div
            className="fixed inset-0 z-60 bg-black/60 backdrop-blur-sm"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={close}
          />

          <div className="fixed inset-0 z-70 flex items-start justify-center px-4 pt-[12vh]">
            <motion.div
              className="premium-panel-strong w-full max-w-2xl overflow-hidden"
              initial={{ opacity: 0, scale: 0.98, y: -14 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.98, y: -14 }}
              transition={{ duration: 0.16, ease: [0.22, 1, 0.36, 1] }}
            >
              <div className="flex items-center gap-3 border-b border-white/8 px-5 py-4">
                <Search className="h-5 w-5 flex-shrink-0 text-surface-400" />
                <input
                  ref={inputRef}
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Search pages, functions, and command surfaces"
                  className="w-full bg-transparent text-sm text-white placeholder:text-surface-500 focus:outline-none"
                />
                <span className="rounded-lg border border-white/10 bg-white/6 px-2 py-1 text-[10px] text-surface-400">
                  ESC
                </span>
              </div>

              <div ref={listRef} className="max-h-[28rem] overflow-y-auto px-2 py-2">
                {filtered.length ? (
                  filtered.map((item, index) => (
                    <button
                      key={item.id}
                      data-index={index}
                      onClick={() => {
                        item.action();
                        close();
                      }}
                      onMouseEnter={() => setActiveIndex(index)}
                      className={cn(
                        "flex w-full items-start gap-3 rounded-2xl border px-3 py-3 text-left transition-all duration-150",
                        index === activeIndex
                          ? "border-brand-400/20 bg-brand-500/15 text-white shadow-glow"
                          : "border-transparent text-surface-300 hover:border-white/8 hover:bg-white/6 hover:text-white",
                      )}
                    >
                      <span className="mt-0.5 flex h-10 w-10 items-center justify-center rounded-2xl border border-white/10 bg-white/6">
                        {item.icon}
                      </span>
                      <span className="min-w-0">
                        <span className="block text-sm font-medium">{item.label}</span>
                        <span className="mt-1 block text-xs text-surface-500">
                          {item.description}
                        </span>
                      </span>
                    </button>
                  ))
                ) : (
                  <div className="px-4 py-10 text-center text-sm text-surface-400">
                    No command surfaces matched "{query}".
                  </div>
                )}
              </div>
            </motion.div>
          </div>
        </>
      ) : null}
    </AnimatePresence>
  );
}
