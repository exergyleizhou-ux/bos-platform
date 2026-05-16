import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

interface BOSAuthShellProps {
  localeLabel: string;
  onToggleLocale: () => void;
  toggleDisabled?: boolean;
  systemName: string;
  systemTagline: string;
  backgroundWordmark: string;
  statusItems: string[];
  sceneOverlay?: ReactNode;
  children: ReactNode;
  immersiveState?: "normal" | "entering" | "immersive" | "exiting";
}

export function BOSAuthShell({
  localeLabel,
  onToggleLocale,
  toggleDisabled = false,
  systemName,
  systemTagline,
  backgroundWordmark,
  statusItems,
  sceneOverlay,
  children,
  immersiveState = "normal",
}: BOSAuthShellProps) {
  return (
    <div data-i18n-skip className="bos-auth-shell" data-immersive-state={immersiveState}>
      <div className="bos-auth-shell__scene" aria-hidden="true">
        <div className="bos-auth-shell__void" />
        <div className="bos-auth-shell__vignette" />
        <div className="bos-auth-shell__wordmark">{backgroundWordmark}</div>
      </div>

      {sceneOverlay}

      <div className="bos-auth-shell__chrome">
        <header className="bos-auth-shell__topbar">
          <div className="bos-auth-shell__brand">
            <div className="bos-auth-shell__brand-mark" />
            <div className="bos-auth-shell__brand-copy">
              <div className="bos-auth-shell__brand-name">{systemName}</div>
              <div className="bos-auth-shell__brand-tagline">{systemTagline}</div>
            </div>
          </div>

          <button
            type="button"
            onClick={onToggleLocale}
            disabled={toggleDisabled}
            data-login-target="toggle-locale"
            className={cn(
              "bos-auth-shell__locale",
              toggleDisabled && "bos-auth-shell__locale--disabled",
            )}
          >
            {localeLabel}
          </button>
        </header>

        <main className="bos-auth-shell__main">
          <div className="bos-auth-shell__card-stage">{children}</div>
        </main>

        <footer className="bos-auth-shell__status">
          {statusItems.map((item) => (
            <div key={item} className="bos-auth-shell__status-item">
              <span className="bos-auth-shell__status-dot" />
              <span>{item}</span>
            </div>
          ))}
        </footer>
      </div>
    </div>
  );
}
