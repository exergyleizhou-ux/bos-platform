import { useState } from "react";
import { ChevronLeft, ChevronRight, Sparkles, Waves, Zap } from "lucide-react";

import type { LoginSceneTelemetry } from "../core/types";
import { NeuralEKG } from "./NeuralEKG";
import { PlasmaBar } from "./PlasmaBar";

type LoginSignalPanelProps = {
  title: string;
  body: string;
  hint: string;
  telemetry: LoginSceneTelemetry;
  metricLabels: {
    signal: string;
    grip: string;
    openness: string;
    arcLoad: string;
    ekg: string;
  };
  guideTitle: string;
  guideItems: Array<{ icon: "spark" | "zap" | "wave"; text: string; preview: string }>;
  collapsed: boolean;
  onToggleGuide?: () => void;
  collapseLabel: string;
  expandLabel: string;
  panelCollapsed: boolean;
  onTogglePanel?: () => void;
  panelCollapseLabel: string;
  panelExpandLabel: string;
};

function renderIcon(icon: "spark" | "zap" | "wave") {
  if (icon === "zap") return <Zap className="h-3.5 w-3.5" />;
  if (icon === "wave") return <Waves className="h-3.5 w-3.5" />;
  return <Sparkles className="h-3.5 w-3.5" />;
}

export function LoginSignalPanel({
  title,
  body,
  hint,
  telemetry,
  metricLabels,
  guideTitle,
  guideItems,
  collapsed,
  onToggleGuide,
  collapseLabel,
  expandLabel,
  panelCollapsed,
  onTogglePanel,
  panelCollapseLabel,
  panelExpandLabel,
}: LoginSignalPanelProps) {
  const [hoveredPreview, setHoveredPreview] = useState<string | null>(null);

  return (
    <aside className={`login-signal-panel ${panelCollapsed ? "is-collapsed" : ""}`}>
      <div className="login-signal-panel__topline">
        <p className="login-signal-panel__eyebrow">Signal Field</p>
        <button
          type="button"
          className="login-immersive__panel-toggle"
          onClick={onTogglePanel}
          aria-label={panelCollapsed ? panelExpandLabel : panelCollapseLabel}
        >
          {panelCollapsed ? (
            <ChevronRight className="h-4 w-4" />
          ) : (
            <ChevronLeft className="h-4 w-4" />
          )}
        </button>
      </div>
      {!panelCollapsed ? (
        <>
          <div className="login-signal-panel__intro">
            <h3 className="login-signal-panel__title">{title}</h3>
            <p className="login-signal-panel__body">{body}</p>
            <p className="login-signal-panel__hint">{hint}</p>
          </div>

          <div className="login-signal-panel__metrics">
            <PlasmaBar label={metricLabels.signal} value={telemetry.signal} />
            <PlasmaBar label={metricLabels.grip} value={telemetry.grip} />
            <PlasmaBar label={metricLabels.openness} value={telemetry.openness} />
            <PlasmaBar label={metricLabels.arcLoad} value={telemetry.arcLoad} />
          </div>

          <div className="login-signal-panel__ekg-wrap">
            <div className="login-signal-panel__ekg-head">
              <span>{metricLabels.ekg}</span>
              <strong>{telemetry.gestureLabel}</strong>
            </div>
            <NeuralEKG signalStrength={telemetry.signal} />
          </div>

          <div className="login-signal-panel__guide">
            <div className="login-signal-panel__guide-head">
              <p>{guideTitle}</p>
              <button type="button" onClick={onToggleGuide}>
                {collapsed ? expandLabel : collapseLabel}
              </button>
            </div>
            <div className="login-signal-panel__guide-preview">
              {hoveredPreview ?? telemetry.gestureLabel}
            </div>
            {!collapsed ? (
              <div className="login-signal-panel__guide-list">
                {guideItems.map((item) => (
                  <div
                    key={item.text}
                    className="login-signal-panel__guide-item"
                    onMouseEnter={() => setHoveredPreview(item.preview)}
                    onMouseLeave={() => setHoveredPreview(null)}
                  >
                    <span className="login-signal-panel__guide-icon">{renderIcon(item.icon)}</span>
                    <span>{item.text}</span>
                  </div>
                ))}
              </div>
            ) : null}
          </div>
        </>
      ) : (
        <div className="login-signal-panel__collapsed-state">
          <div className="login-signal-panel__collapsed-note">{guideTitle}</div>
          <div className="login-signal-panel__collapsed-preview">
            <strong>{title}</strong>
            <span>
              {metricLabels.signal}: {telemetry.signal}%
            </span>
          </div>
        </div>
      )}
    </aside>
  );
}
