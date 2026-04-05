/**
 * BOS Pipeline v9.0 �� Keyboard Shortcut Hook
 *
 * Global keyboard shortcut listener for the BOS application.
 */

import { useEffect, useCallback } from "react";

interface BOSShortcutHandlers {
  onSearch?: () => void;        // ?K / Ctrl+K
  onToggleSidebar?: () => void; // ?B / Ctrl+B
  onToggleTheme?: () => void;   // ?Shift+T
  onEscape?: () => void;        // Escape
  onNewBatch?: () => void;      // ?N / Ctrl+N
}

/**
 * Registers global keyboard shortcuts for the BOS Pipeline application.
 */
export function useBOSShortcuts(handlers: BOSShortcutHandlers) {
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      const isMod = e.metaKey || e.ctrlKey;
      const target = e.target as HTMLElement;

      // Skip if user is typing in an input field
      if (
        target.tagName === "INPUT" ||
        target.tagName === "TEXTAREA" ||
        target.tagName === "SELECT" ||
        target.isContentEditable
      ) {
        // Allow Escape even in inputs
        if (e.key === "Escape" && handlers.onEscape) {
          e.preventDefault();
          handlers.onEscape();
        }
        return;
      }

      // ?K / Ctrl+K �� Search / Command Palette
      if (isMod && e.key === "k") {
        e.preventDefault();
        handlers.onSearch?.();
        return;
      }

      // ?B / Ctrl+B �� Toggle Sidebar
      if (isMod && e.key === "b") {
        e.preventDefault();
        handlers.onToggleSidebar?.();
        return;
      }

      // ?Shift+T �� Toggle Theme
      if (isMod && e.shiftKey && e.key === "T") {
        e.preventDefault();
        handlers.onToggleTheme?.();
        return;
      }

      // ?N / Ctrl+N �� New Batch
      if (isMod && e.key === "n") {
        e.preventDefault();
        handlers.onNewBatch?.();
        return;
      }

      // Escape �� Close overlays
      if (e.key === "Escape") {
        handlers.onEscape?.();
        return;
      }
    },
    [handlers],
  );

  useEffect(() => {
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);
}

/**
 * Generic single-key shortcut hook.
 */
export function useKeyboardShortcut(
  key: string,
  callback: () => void,
  options?: {
    ctrl?: boolean;
    meta?: boolean;
    shift?: boolean;
    alt?: boolean;
    skipInputs?: boolean;
  },
) {
  const {
    ctrl = false,
    meta = false,
    shift = false,
    alt = false,
    skipInputs = true,
  } = options ?? {};

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (skipInputs) {
        const target = e.target as HTMLElement;
        if (
          target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.tagName === "SELECT" ||
          target.isContentEditable
        ) {
          return;
        }
      }

      const modMatch =
        (!ctrl || e.ctrlKey) &&
        (!meta || e.metaKey) &&
        (!shift || e.shiftKey) &&
        (!alt || e.altKey);

      if (modMatch && e.key === key) {
        e.preventDefault();
        callback();
      }
    };

    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [key, callback, ctrl, meta, shift, alt, skipInputs]);
}
