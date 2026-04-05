import type { ReactNode } from "react";

import {
  Beaker,
  Calculator,
  Cpu,
  LayoutDashboard,
  Leaf,
  Settings,
  ShieldCheck,
  Shuffle,
  TrendingUp,
} from "lucide-react";

export interface AppNavItem {
  to: string;
  label: string;
  shortLabel: string;
  description: string;
  icon: ReactNode;
  section: string;
  minRole?: string;
  keywords?: string[];
}

export const NAV_ITEMS: AppNavItem[] = [
  {
    to: "/dashboard",
    label: "Executive Overview",
    shortLabel: "Overview",
    description: "System posture, alerts, and release momentum.",
    icon: <LayoutDashboard className="h-5 w-5" />,
    section: "Command",
    keywords: ["overview", "home", "alerts", "executive"],
  },
  {
    to: "/batches",
    label: "Batch Command",
    shortLabel: "Batches",
    description: "Inspect live and historical batch command surfaces.",
    icon: <Beaker className="h-5 w-5" />,
    section: "Operations",
    keywords: ["batch", "command", "queue", "records"],
  },
  {
    to: "/ser",
    label: "SER Compute",
    shortLabel: "SER",
    description: "Run matched-boundary performance calculations.",
    icon: <Calculator className="h-5 w-5" />,
    section: "Analysis",
    keywords: ["ser", "compute", "efficiency", "grade"],
  },
  {
    to: "/simulation",
    label: "Simulation",
    shortLabel: "Simulation",
    description: "Stress-test outcome ranges and sensitivities.",
    icon: <Shuffle className="h-5 w-5" />,
    section: "Analysis",
    keywords: ["simulation", "sensitivity", "monte carlo"],
  },
  {
    to: "/forecast",
    label: "Forecast",
    shortLabel: "Forecast",
    description: "Trend signals, drift, and upcoming release pressure.",
    icon: <TrendingUp className="h-5 w-5" />,
    section: "Analysis",
    keywords: ["forecast", "predict", "trend"],
  },
  {
    to: "/twins",
    label: "Digital Twins",
    shortLabel: "Twins",
    description: "Inspect digital twin state and scenario projections.",
    icon: <Cpu className="h-5 w-5" />,
    section: "Intelligence",
    keywords: ["twin", "model", "digital twin"],
  },
  {
    to: "/sustainability",
    label: "Sustainability",
    shortLabel: "Ledger",
    description: "Review qualified water, energy, and GHG implications.",
    icon: <Leaf className="h-5 w-5" />,
    section: "Intelligence",
    keywords: ["sustainability", "ghg", "water", "energy", "tea"],
  },
  {
    to: "/settings",
    label: "Operator Settings",
    shortLabel: "Settings",
    description: "Identity, access posture, and console presentation controls.",
    icon: <Settings className="h-5 w-5" />,
    section: "System",
    keywords: ["settings", "preferences", "theme", "profile", "access"],
  },
  {
    to: "/admin",
    label: "Control Room",
    shortLabel: "Admin",
    description: "Runtime health, operator governance, and feature-gate posture.",
    icon: <ShieldCheck className="h-5 w-5" />,
    section: "System",
    minRole: "admin",
    keywords: ["admin", "users", "governance", "runtime", "flags"],
  },
];

export function findNavItem(pathname: string) {
  return NAV_ITEMS.find((item) => pathname.startsWith(item.to));
}
