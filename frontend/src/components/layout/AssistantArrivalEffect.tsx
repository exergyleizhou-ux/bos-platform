import { useEffect, useState } from "react";

import { useUIStore } from "@/store/uiStore";

type ArrivalBurst = NonNullable<
  ReturnType<typeof useUIStore.getState>["assistantArrivalBurst"]
>;

export function AssistantArrivalEffect() {
  const burst = useUIStore((state) => state.assistantArrivalBurst);
  const clearAssistantArrivalBurst = useUIStore((state) => state.clearAssistantArrivalBurst);
  const [activeBurst, setActiveBurst] = useState<ArrivalBurst | null>(null);

  useEffect(() => {
    if (!burst) return;
    if (Date.now() - burst.createdAt > 9000) {
      clearAssistantArrivalBurst();
      return;
    }

    setActiveBurst(burst);
    clearAssistantArrivalBurst();

    const timer = window.setTimeout(() => {
      setActiveBurst(null);
    }, 2400);

    return () => window.clearTimeout(timer);
  }, [burst, clearAssistantArrivalBurst]);

  if (!activeBurst) return null;

  return (
    <div
      className="assistant-arrival-burst"
      aria-hidden="true"
      style={{ ["--assistant-arrival-amplitude" as string]: String(activeBurst.amplitude) }}
    >
      <span className="assistant-arrival-burst__flare" />
      <span className="assistant-arrival-burst__ring assistant-arrival-burst__ring--outer" />
      <span className="assistant-arrival-burst__ring assistant-arrival-burst__ring--inner" />
      <span className="assistant-arrival-burst__beam assistant-arrival-burst__beam--left" />
      <span className="assistant-arrival-burst__beam assistant-arrival-burst__beam--right" />
      <span className="assistant-arrival-burst__rail assistant-arrival-burst__rail--title" />
      <span className="assistant-arrival-burst__rail assistant-arrival-burst__rail--sigil" />
      <span className="assistant-arrival-burst__node assistant-arrival-burst__node--title" />
      <span className="assistant-arrival-burst__node assistant-arrival-burst__node--sigil" />
      <span className="assistant-arrival-burst__arc assistant-arrival-burst__arc--a" />
      <span className="assistant-arrival-burst__arc assistant-arrival-burst__arc--b" />
      <span className="assistant-arrival-burst__spark assistant-arrival-burst__spark--a" />
      <span className="assistant-arrival-burst__spark assistant-arrival-burst__spark--b" />
      <span className="assistant-arrival-burst__spark assistant-arrival-burst__spark--c" />
    </div>
  );
}
