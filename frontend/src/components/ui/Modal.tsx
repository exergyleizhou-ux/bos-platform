import { useEffect, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { AnimatePresence, motion } from "framer-motion";
import { X } from "lucide-react";

import { cn } from "@/lib/utils";

interface ModalProps {
  open: boolean;
  onClose: () => void;
  title?: string;
  description?: string;
  children: ReactNode;
  footer?: ReactNode;
  size?: "sm" | "md" | "lg" | "xl";
  closeOnBackdrop?: boolean;
  className?: string;
}

const SIZE_MAP = {
  sm: "max-w-sm",
  md: "max-w-md",
  lg: "max-w-lg",
  xl: "max-w-xl",
} as const;

export function Modal({
  open,
  onClose,
  title,
  description,
  children,
  footer,
  size = "md",
  closeOnBackdrop = true,
  className,
}: ModalProps) {
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (open && panelRef.current) {
      const focusable = panelRef.current.querySelector<HTMLElement>(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
      );
      focusable?.focus();
    }
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const handler = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, onClose]);

  useEffect(() => {
    document.body.style.overflow = open ? "hidden" : "";
    return () => {
      document.body.style.overflow = "";
    };
  }, [open]);

  return createPortal(
    <AnimatePresence>
      {open ? (
        <>
          <motion.div
            key="modal-backdrop"
            className="fixed inset-0 z-60 bg-black/60 backdrop-blur-sm"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            onClick={closeOnBackdrop ? onClose : undefined}
            aria-hidden="true"
          />

          <div className="fixed inset-0 z-70 flex items-center justify-center p-4">
            <motion.div
              ref={panelRef}
              key="modal-panel"
              role="dialog"
              aria-modal="true"
              aria-labelledby={title ? "modal-title" : undefined}
              aria-describedby={description ? "modal-desc" : undefined}
              className={cn(
                "premium-panel-strong glass-border w-full",
                SIZE_MAP[size],
                className,
              )}
              initial={{ opacity: 0, scale: 0.96, y: 10 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.96, y: 10 }}
              transition={{ duration: 0.16 }}
              onClick={(event) => event.stopPropagation()}
            >
              {(title || description) ? (
                <div className="flex items-start justify-between gap-4 border-b border-white/8 px-6 py-4">
                  <div>
                    {title ? (
                      <h2 id="modal-title" className="text-lg font-semibold text-white">
                        {title}
                      </h2>
                    ) : null}
                    {description ? (
                      <p id="modal-desc" className="mt-0.5 text-sm text-surface-400">
                        {description}
                      </p>
                    ) : null}
                  </div>
                  <button
                    onClick={onClose}
                    className="rounded-2xl border border-white/10 bg-white/6 p-2 text-surface-400 transition-colors hover:text-white"
                    aria-label="Close"
                  >
                    <X className="h-5 w-5" />
                  </button>
                </div>
              ) : null}

              <div className="px-6 py-5">{children}</div>

              {footer ? (
                <div className="flex items-center justify-end gap-3 border-t border-white/8 px-6 py-4">
                  {footer}
                </div>
              ) : null}
            </motion.div>
          </div>
        </>
      ) : null}
    </AnimatePresence>,
    document.body,
  );
}
