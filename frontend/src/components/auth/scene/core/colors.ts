export const BOS_COLORS = {
  void: "#06080A",
  deepSpace: "#090B0D",
  neuralCyan: "#00C8D4",
  plasmaGreen: "#00FF9D",
  currentGold: "#1AFFE4",
  dangerRed: "#FF3B5C",
  textPrimary: "#B8E8EC",
  textSecondary: "#82BEC8",
  textHint: "rgba(80, 140, 150, 0.45)",
  cyanGlass: "rgba(0, 200, 212, 0.06)",
  cyanBorder: "rgba(0, 200, 212, 0.18)",
  cyanGlow: "rgba(0, 200, 212, 0.4)",
  goldGlow: "rgba(26, 255, 228, 0.4)",
  plasmaGlow: "rgba(0, 255, 157, 0.4)",
} as const;

export const ARC_COLORS = [
  BOS_COLORS.neuralCyan,
  BOS_COLORS.currentGold,
  "#80FFF5",
] as const;
