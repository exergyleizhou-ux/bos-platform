/**
 * BOS Pipeline v9.0 loading screen.
 *
 * Full-screen loading overlay used during auth checks and lazy route loading.
 */

import { BOSSigil } from "@/components/ui/BOSSigil";
import { translateText } from "@/lib/i18n";

interface LoadingScreenProps {
  label?: string;
}

export function LoadingScreen({ label = "Loading..." }: LoadingScreenProps) {
  return (
    <div className="loading-sanctuary flex min-h-screen items-center justify-center overflow-hidden px-6 py-10">
      <div className="loading-grid opacity-60" />
      <div className="loading-scanline" />

      <div className="relative z-[1] flex w-full max-w-xl flex-col items-center text-center">
        <BOSSigil showGlyph />

        <div className="mt-10 space-y-3">
          <p className="text-[0.72rem] font-semibold uppercase tracking-[0.42em] text-surface-500">
            {translateText("BOS Assistant")}
          </p>
          <h1 className="font-display text-5xl font-semibold tracking-[0.18em] text-white">
            BOS
          </h1>
          <p className="mx-auto max-w-md text-sm leading-7 text-surface-300">
            {translateText("Clarity arrives before motion.")}
          </p>
        </div>

        <div className="mt-8 inline-flex items-center gap-3 rounded-full border border-white/10 bg-white/6 px-5 py-2.5 text-sm text-surface-200 backdrop-blur-md">
          <span className="assistant-stream-cursor" />
          <span>{translateText(label)}</span>
        </div>
      </div>
    </div>
  );
}
