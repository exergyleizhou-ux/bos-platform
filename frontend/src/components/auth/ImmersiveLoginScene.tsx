import { useEffect, useMemo, useRef, useState } from "react";
import type { CSSProperties } from "react";
import type { HandLandmarker, NormalizedLandmark } from "@mediapipe/tasks-vision";
import {
  Camera,
  ChevronLeft,
  ChevronRight,
  Hand,
  Languages,
  Loader2,
  TriangleAlert,
} from "lucide-react";

import { getBreathController } from "@/components/auth/scene/core/breath";
import { clamp01, lerp, randomBetween } from "@/components/auth/scene/core/math";
import type { GestureFrame, LoginSceneTelemetry, Point2D } from "@/components/auth/scene/core/types";
import { createEmptyGestureFrame, GestureController } from "@/components/auth/scene/gestures/gestureController";
import { detectGestureCandidate } from "@/components/auth/scene/gestures/gestureDetection";
import { AtmosphereLayer } from "@/components/auth/scene/layers/atmosphereLayer";
import { ElectricArcsLayer } from "@/components/auth/scene/layers/electricArcsLayer";
import { PCBTraceLayer } from "@/components/auth/scene/layers/pcbTraceLayer";
import { ReactorCoreLayer } from "@/components/auth/scene/layers/reactorCoreLayer";
import {
  createSceneRenderer,
  type BOSSceneSummary,
  type ImmersiveSceneRenderer,
} from "@/components/auth/scene/splat/rendererBackend";
import { getSceneNeighbor } from "@/components/auth/scene/splat/sceneTopology";
import { LoginSignalPanel } from "@/components/auth/scene/ui/LoginSignalPanel";
import { Button } from "@/components/ui/Button";
import { useI18n } from "@/providers/I18nProvider";
import "@/styles/login-immersive.css";

export type CameraState = "idle" | "loading" | "ready" | "denied" | "error";
type CameraStage = "idle" | "requesting" | "binding" | "model";
type CameraPermissionState = "prompt" | "granted" | "denied" | "unsupported" | "unknown";

type SceneCopy = {
  panelTitle: string;
  panelBody: string;
  panelHint: string;
  metricSignal: string;
  metricGrip: string;
  metricOpenness: string;
  metricArcLoad: string;
  metricEkg: string;
  guideTitle: string;
  guideCollapse: string;
  guideExpand: string;
  guideOpenPalm: string;
  guideFist: string;
  guidePoint: string;
  guidePeace: string;
  guidePinch: string;
  guideSwipe: string;
  guideCircle: string;
  guideThumbs: string;
  guideBigBang: string;
  guideRotation: string;
  guidePush: string;
  guideSpread: string;
  collapseSignal: string;
  expandSignal: string;
  collapseCamera: string;
  expandCamera: string;
  cameraIdle: string;
  cameraLoading: string;
  cameraRequesting: string;
  cameraBinding: string;
  cameraModelLoading: string;
  cameraReady: string;
  cameraDenied: string;
  cameraError: string;
  cameraInsecure: string;
  cameraPromptTimeout: string;
  cameraStreamTimeout: string;
  cameraNoDevice: string;
  cameraBusy: string;
  enableCamera: string;
  retryCamera: string;
  handDetected: string;
  fallbackMode: string;
  permissionHint: string;
  permissionStateLabel: string;
  permissionPrompt: string;
  permissionGranted: string;
  permissionDenied: string;
  permissionUnsupported: string;
  permissionUnknown: string;
  cameraRememberOn: string;
  cameraRememberOff: string;
  gestureIdle: string;
  gestureOpenPalm: string;
  gestureFist: string;
  gesturePoint: string;
  gesturePeace: string;
  gesturePinch: string;
  gestureSwipe: string;
  gestureCircle: string;
  gestureThumbs: string;
  gestureBigBang: string;
  gestureRotation: string;
  gesturePush: string;
  gestureSpread: string;
};

type SceneLayers = {
  atmosphere: AtmosphereLayer;
  pcb: PCBTraceLayer;
  reactor: ReactorCoreLayer;
  arcs: ElectricArcsLayer;
};

type ImmersiveLoginSceneProps = {
  entering?: boolean;
  immersiveState?: "normal" | "entering" | "immersive" | "exiting";
  autoStartCamera?: boolean;
  onAutoStartCameraChange?: (enabled: boolean) => void;
  guideCollapsed?: boolean;
  onToggleGuide?: () => void;
  onTogglePassword?: () => void;
  onToggleLocale?: () => void;
  onClearField?: (target: "username" | "password") => void;
  onClearAll?: () => void;
  onEnterImmersive?: () => void;
  onExitImmersive?: () => void;
  onSubmitGesture?: () => void;
  formReady?: boolean;
  reducedMotion?: boolean;
};

export type SceneTransitionKind = "page-left" | "page-right" | "dive" | "portal" | "shatter";

export type SceneTransitionProfile = {
  durationMs: number;
  ringScale: number;
  washScale: number;
  washOpacity: number;
  edgeWidth: string;
  snapshotBlurPx: number;
  shardOpacity: number;
  focusX: number;
  focusY: number;
  charge: number;
  snapshotClipStart: string;
  snapshotClipEnd: string;
  apertureOpacity: number;
  apertureScale: number;
  motionScale: number;
};

const SCENE_TRANSITION_BIAS: Record<
  string,
  { tempo: number; focusX: number; focusY: number; ringScale: number; washScale: number }
> = {
  neural_core: { tempo: 0.96, focusX: 0.5, focusY: 0.42, ringScale: 0.92, washScale: 0.98 },
  reactor_interior: { tempo: 1.02, focusX: 0.5, focusY: 0.58, ringScale: 1.08, washScale: 1.04 },
  synaptic_web: { tempo: 1.04, focusX: 0.6, focusY: 0.48, ringScale: 1.02, washScale: 1.06 },
  data_void: { tempo: 1.1, focusX: 0.44, focusY: 0.52, ringScale: 1.16, washScale: 1.14 },
  bio_matrix: { tempo: 0.98, focusX: 0.53, focusY: 0.46, ringScale: 1.04, washScale: 1.08 },
};

function clampTransitionUnit(value: number) {
  return Math.max(0.1, Math.min(0.9, value));
}

function formatPercent(value: number) {
  return `${(clampTransitionUnit(value) * 100).toFixed(2)}%`;
}

function getTransitionClipProfile(
  kind: SceneTransitionKind | null,
  focusX: number,
  focusY: number,
  charge: number,
) {
  const fx = formatPercent(focusX);
  const fy = formatPercent(focusY);

  if (kind === "portal") {
    return {
      snapshotClipStart: `circle(${(8 + charge * 3).toFixed(2)}% at ${fx} ${fy})`,
      snapshotClipEnd: `circle(${(102 + charge * 10).toFixed(2)}% at ${fx} ${fy})`,
      apertureOpacity: 0.62 + charge * 0.12,
      apertureScale: 1.02 + charge * 0.08,
    };
  }

  if (kind === "dive") {
    return {
      snapshotClipStart: `ellipse(${(18 + charge * 4).toFixed(2)}% ${(12 + charge * 3).toFixed(2)}% at ${fx} ${fy})`,
      snapshotClipEnd: `ellipse(${(106 + charge * 8).toFixed(2)}% ${(94 + charge * 8).toFixed(2)}% at ${fx} ${fy})`,
      apertureOpacity: 0.76 + charge * 0.1,
      apertureScale: 1.18 + charge * 0.1,
    };
  }

  if (kind === "shatter") {
    return {
      snapshotClipStart: `polygon(8% 10%, 88% 4%, 96% 38%, 88% 90%, 22% 98%, 4% 60%, 14% 20%)`,
      snapshotClipEnd: `polygon(0 0, 100% 0, 82% 22%, 100% 48%, 74% 100%, 18% 86%, 0 58%, 12% 18%)`,
      apertureOpacity: 0.58 + charge * 0.16,
      apertureScale: 1.1 + charge * 0.12,
    };
  }

  if (kind === "page-left" || kind === "page-right") {
    return {
      snapshotClipStart: `inset(0 round 0)`,
      snapshotClipEnd: `inset(0 0 0 0 round 0)`,
      apertureOpacity: 0.28 + charge * 0.08,
      apertureScale: 1,
    };
  }

  return {
    snapshotClipStart: `inset(0 round 0)`,
    snapshotClipEnd: `inset(0 round 0)`,
    apertureOpacity: 0.24 + charge * 0.06,
    apertureScale: 1,
  };
}

function clampTransitionCharge(value: number) {
  return Math.max(0, Math.min(1.25, value));
}

export function getTransitionCharge(
  telemetry: LoginSceneTelemetry,
  gestureConfidence: number,
  cameraState: CameraState,
  immersiveState: ImmersiveLoginSceneProps["immersiveState"],
) {
  const telemetryCharge =
    telemetry.energy / 100 * 0.4 +
    telemetry.signal / 100 * 0.22 +
    telemetry.grip / 100 * 0.2 +
    telemetry.openness / 100 * 0.18;
  const cameraCharge =
    cameraState === "ready"
      ? 0.14
      : cameraState === "loading"
        ? 0.08
        : cameraState === "denied"
          ? -0.04
          : cameraState === "error"
            ? -0.08
            : 0;
  const immersiveCharge =
    immersiveState === "entering"
      ? 0.08
      : immersiveState === "exiting"
        ? 0.12
        : immersiveState === "immersive"
          ? 0.05
          : 0;
  return clampTransitionCharge(telemetryCharge + gestureConfidence * 0.22 + cameraCharge + immersiveCharge);
}

export function getSceneTransitionProfile(
  kind: SceneTransitionKind | null,
  sceneId: string | undefined,
  direction: 1 | -1,
  focus: Point2D,
  telemetry: LoginSceneTelemetry,
  gestureConfidence: number,
  cameraState: CameraState,
  immersiveState: ImmersiveLoginSceneProps["immersiveState"],
  reducedMotion: boolean,
): SceneTransitionProfile {
  const sceneBias = sceneId ? SCENE_TRANSITION_BIAS[sceneId] : undefined;
  const charge = getTransitionCharge(telemetry, gestureConfidence, cameraState, immersiveState);
  const tempo = sceneBias?.tempo ?? 1;
  const baseFocusX = sceneBias?.focusX ?? 0.5;
  const baseFocusY = sceneBias?.focusY ?? 0.5;
  const directedFocusX =
    kind === "page-left" || kind === "page-right"
      ? baseFocusX + (direction > 0 ? 0.05 : -0.05)
      : baseFocusX;
  const blendedFocusX = clampTransitionUnit(focus.x * (0.34 + charge * 0.08) + directedFocusX * (0.66 - charge * 0.08));
  const blendedFocusY = clampTransitionUnit(focus.y * (0.34 + charge * 0.08) + baseFocusY * (0.66 - charge * 0.08));
  const clipProfile = getTransitionClipProfile(kind, blendedFocusX, blendedFocusY, charge);
  const motionScale = reducedMotion ? 0.18 : 1;
  const reducedDurationMultiplier = reducedMotion ? 0.72 : 1;
  const reducedCharge = reducedMotion ? charge * 0.42 : charge;

  if (kind === "portal") {
    return {
      durationMs: Math.round(860 * tempo * (1.02 - reducedCharge * 0.06) * reducedDurationMultiplier),
      ringScale: 1 + (5.2 * (sceneBias?.ringScale ?? 1) * (1 + reducedCharge * 0.08) - 1) * motionScale,
      washScale: 1 + (1.08 * (sceneBias?.washScale ?? 1) * (1 + reducedCharge * 0.06) - 1) * motionScale,
      washOpacity: reducedMotion ? 0.42 : 0.9 + reducedCharge * 0.06,
      edgeWidth: "18%",
      snapshotBlurPx: reducedMotion ? 0 : Math.round(12 + reducedCharge * 4),
      shardOpacity: reducedMotion ? 0.04 : 0.2 + reducedCharge * 0.08,
      focusX: blendedFocusX,
      focusY: blendedFocusY,
      charge: reducedCharge,
      ...clipProfile,
      apertureOpacity: reducedMotion ? 0.22 : clipProfile.apertureOpacity,
      apertureScale: 1 + (clipProfile.apertureScale - 1) * motionScale,
      motionScale,
    };
  }

  if (kind === "dive") {
    return {
      durationMs: Math.round(980 * tempo * (1.05 - reducedCharge * 0.04) * reducedDurationMultiplier),
      ringScale: 1 + (6.1 * (sceneBias?.ringScale ?? 1) * (1 + reducedCharge * 0.1) - 1) * motionScale,
      washScale: 1 + (1.16 * (sceneBias?.washScale ?? 1) * (1 + reducedCharge * 0.09) - 1) * motionScale,
      washOpacity: reducedMotion ? 0.46 : 0.94 + reducedCharge * 0.04,
      edgeWidth: "16%",
      snapshotBlurPx: reducedMotion ? 0 : Math.round(16 + reducedCharge * 6),
      shardOpacity: reducedMotion ? 0.08 : 0.9 + reducedCharge * 0.12,
      focusX: blendedFocusX,
      focusY: blendedFocusY,
      charge: reducedCharge,
      ...clipProfile,
      apertureOpacity: reducedMotion ? 0.24 : clipProfile.apertureOpacity,
      apertureScale: 1 + (clipProfile.apertureScale - 1) * motionScale,
      motionScale,
    };
  }

  if (kind === "shatter") {
    return {
      durationMs: Math.round(780 * tempo * (1 - reducedCharge * 0.08) * reducedDurationMultiplier),
      ringScale: 1 + (4.3 * (sceneBias?.ringScale ?? 1) * (1 + reducedCharge * 0.06) - 1) * motionScale,
      washScale: 1 + (1.02 * (sceneBias?.washScale ?? 1) * (1 + reducedCharge * 0.04) - 1) * motionScale,
      washOpacity: reducedMotion ? 0.4 : 0.86 + reducedCharge * 0.05,
      edgeWidth: reducedCharge > 0.72 ? "26%" : "22%",
      snapshotBlurPx: reducedMotion ? 0 : Math.round(6 + reducedCharge * 3),
      shardOpacity: reducedMotion ? 0.05 : 1.04 + reducedCharge * 0.18,
      focusX: blendedFocusX,
      focusY: blendedFocusY,
      charge: reducedCharge,
      ...clipProfile,
      apertureOpacity: reducedMotion ? 0.18 : clipProfile.apertureOpacity,
      apertureScale: 1 + (clipProfile.apertureScale - 1) * motionScale,
      motionScale,
    };
  }

  return {
    durationMs: Math.round(740 * tempo * (1 - reducedCharge * 0.05) * reducedDurationMultiplier),
    ringScale: 1 + (4 * (sceneBias?.ringScale ?? 1) * (1 + reducedCharge * 0.04) - 1) * motionScale,
    washScale: 1 + (1 * (sceneBias?.washScale ?? 1) * (1 + reducedCharge * 0.04) - 1) * motionScale,
    washOpacity: reducedMotion ? 0.32 : 0.82 + reducedCharge * 0.05,
    edgeWidth: reducedCharge > 0.7 ? "30%" : "28%",
    snapshotBlurPx: reducedMotion ? 0 : Math.round(8 + reducedCharge * 3),
    shardOpacity: reducedMotion ? 0.03 : 0.28 + reducedCharge * 0.12,
    focusX: blendedFocusX,
    focusY: blendedFocusY,
    charge: reducedCharge,
    ...clipProfile,
    apertureOpacity: reducedMotion ? 0.14 : clipProfile.apertureOpacity,
    apertureScale: 1 + (clipProfile.apertureScale - 1) * motionScale,
    motionScale,
  };
}

const COMBO_SEQUENCES = [
  {
    label: "Neural Calibration",
    sequence: ["FIST", "OPEN_PALM", "THUMBS_UP"] as const,
    window: 800,
  },
  {
    label: "Lightning Storm",
    sequence: ["SWIPE_LEFT", "SWIPE_RIGHT", "SWIPE_LEFT"] as const,
    window: 1200,
  },
  {
    label: "Vortex Big Bang",
    sequence: ["CIRCLE", "BOTH_HANDS_OPEN"] as const,
    window: 2000,
  },
];

const SCENE_ANNOTATIONS: Record<
  string,
  {
    en: string[];
    zh: string[];
  }
> = {
  neural_core: {
    en: ["Dense cognition hub", "High-reactivity signal shell", "Recommended: hold scene and inspect the core"],
    zh: ["高密度认知核心", "高反应信号外壳", "建议：定格场景后观察核心层"],
  },
  reactor_interior: {
    en: ["Tri-arm energy lattice", "Core pressure channels", "Best explored with push/pull depth control"],
    zh: ["三臂能量晶格", "核心压力通道", "适合配合推掌与拉掌观察深度"],
  },
  synaptic_web: {
    en: ["Sparse synapse bridges", "Large empty cavities", "Rotation reveals long-range links"],
    zh: ["稀疏突触桥", "大尺度空腔", "旋腕可更明显看到长距离连接"],
  },
  data_void: {
    en: ["Minimal stream geometry", "High-contrast singularity focus", "Use depth navigation to feel isolation"],
    zh: ["极简数据流几何", "高对比奇点焦点", "建议用深度导航感受孤立感"],
  },
  bio_matrix: {
    en: ["Ordered bio lattice", "Organic membrane halo", "Annotations help reveal structural rhythm"],
    zh: ["规整生物晶格", "有机膜层光晕", "打开注释更容易理解结构节律"],
  },
};

const BOOKMARK_STORAGE_KEY = "bos-login-scene-bookmarks";

const CAMERA_WASM_BASE = "/mediapipe/wasm";
const HAND_MODEL_ASSET = "/mediapipe/hand_landmarker.task";
const HAND_CONNECTIONS: Array<[number, number]> = [
  [0, 1],
  [1, 2],
  [2, 3],
  [3, 4],
  [0, 5],
  [5, 6],
  [6, 7],
  [7, 8],
  [5, 9],
  [9, 10],
  [10, 11],
  [11, 12],
  [9, 13],
  [13, 14],
  [14, 15],
  [15, 16],
  [13, 17],
  [0, 17],
  [17, 18],
  [18, 19],
  [19, 20],
];

const HUD_COPY = {
  "en-US": {
    panelTitle: "Reactor bus online",
    panelBody: "The login shell is running on a live PCB field. Every gesture feeds current into the reactor core and trace network.",
    panelHint: "Open palm expands the field, fist compresses the core, thumbs up confirms identity.",
    metricSignal: "Trace drag",
    metricGrip: "Core grip",
    metricOpenness: "Field spread",
    metricArcLoad: "Arc load",
    metricEkg: "Core EKG",
    guideTitle: "Control map",
    guideCollapse: "Hide guide",
    guideExpand: "Show guide",
    guideOpenPalm: "Open palm: widen the reactor breath and brighten the outer rings.",
    guideFist: "Fist: compress the core, hold pressure, then release an arc burst.",
    guidePoint: "Index point: exit immersive mode and return to the mini login card.",
    guidePeace: "Peace sign: hold a stable arc between two fingertips.",
    guidePinch: "Pinch: compress a local node cluster and energize the core.",
    guideSwipe: "Swipe: launch a board-wide current sweep across the shell.",
    guideCircle: "Circle: seed a ring discharge and fan arcs outward.",
    guideThumbs: "Thumbs up: arm the confirmation pulse and submit when ready.",
    guideBigBang: "Both hands open: trigger a singularity build-up and reactor burst.",
    guideRotation: "Wrist rotation: tune the signal field and pulse cadence.",
    guidePush: "Forward push: drive a packet burst into the core. Pull back to exit immersive mode.",
    guideSpread: "Two-hand spread: stretch the reactor field and tension lines.",
    collapseSignal: "Collapse signal panel",
    expandSignal: "Expand signal panel",
    collapseCamera: "Collapse camera panel",
    expandCamera: "Expand camera panel",
    cameraIdle: "Camera is on standby.",
    cameraLoading: "Starting hand-tracking camera...",
    cameraRequesting: "Requesting camera permission...",
    cameraBinding: "Binding live video stream...",
    cameraModelLoading: "Loading local hand model...",
    cameraReady: "Hand-tracking camera is live.",
    cameraDenied: "Camera access was denied.",
    cameraError: "Camera hand tracking is unavailable right now.",
    cameraInsecure: "Camera needs localhost or HTTPS to open.",
    cameraPromptTimeout: "Camera permission request timed out. Check the browser prompt or another app using the camera.",
    cameraStreamTimeout: "Camera permission is granted, but the video stream did not start in time.",
    cameraNoDevice: "No camera device is currently visible to the browser.",
    cameraBusy: "The camera appears busy or unavailable to this browser session.",
    enableCamera: "Enable hand camera",
    retryCamera: "Retry camera",
    handDetected: "Hand lock",
    fallbackMode: "Fallback input",
    permissionHint: "If access is blocked, the page keeps responding to mouse interaction.",
    permissionStateLabel: "Permission",
    permissionPrompt: "Awaiting approval",
    permissionGranted: "Granted",
    permissionDenied: "Denied",
    permissionUnsupported: "No API",
    permissionUnknown: "Unknown",
    cameraRememberOn: "Camera auto-start is remembered.",
    cameraRememberOff: "Camera will stay manual until you enable it again.",
    gestureIdle: "Control router ready.",
    gestureOpenPalm: "Open palm widened the reactor breath and outer field.",
    gestureFist: "Core compression armed. Release to discharge the shell.",
    gesturePoint: "Focused charge locked on a trace target.",
    gesturePeace: "Dual-finger arc stabilized between the fingertips.",
    gesturePinch: "Node compression forming at the focal point.",
    gestureSwipe: "Current sweep launched across the board.",
    gestureCircle: "Ring discharge generator deployed.",
    gestureThumbs: "Identity confirmation pulse accepted.",
    gestureBigBang: "Singularity sequence initiated.",
    gestureRotation: "Wrist rotation tuned the signal field.",
    gesturePush: "Forward push transmitted a packet burst to the core.",
    gestureSpread: "Two-hand spread expanded the reactor field.",
  },
  "zh-CN": {
    panelTitle: "反应堆总线在线",
    panelBody: "登录场景现在像一块活体神经板，每个手势都会把不同的能量注入反应堆核心。",
    panelHint: "张掌扩场，握拳压缩，点赞确认身份。",
    metricSignal: "信号牵引",
    metricGrip: "核心握持",
    metricOpenness: "场域展开",
    metricArcLoad: "电弧负载",
    metricEkg: "核心 EKG",
    guideTitle: "手势地图",
    guideCollapse: "隐藏指南",
    guideExpand: "显示指南",
    guideOpenPalm: "张掌：扩大反应堆呼吸并点亮外环。",
    guideFist: "握拳：压缩核心并蓄力，松开后释放电弧。",
    guidePoint: "单指：退出沉浸并返回右下角登录浮窗。",
    guidePeace: "V 手势：在两指之间保持稳定电弧。",
    guidePinch: "捏合：压缩局部节点簇并提升核心压力。",
    guideSwipe: "横扫：沿整块电路板发射一次电流扫线。",
    guideCircle: "画圈：生成环形放电并向外扇出。",
    guideThumbs: "点赞：触发确认脉冲，准备好时提交登录。",
    guideBigBang: "双手张开：触发奇点蓄能和全场爆发。",
    guideRotation: "旋腕：调节信号场与脉冲节奏。",
    guidePush: "前推：向核心发射一组数据包。拉掌：退出沉浸并返回登录浮窗。",
    guideSpread: "双手外拉：扩张反应堆场域和张力线。",
    collapseSignal: "收起信号面板",
    expandSignal: "展开信号面板",
    collapseCamera: "收起摄像头面板",
    expandCamera: "展开摄像头面板",
    cameraIdle: "摄像头待命中。",
    cameraLoading: "正在启动手势摄像头...",
    cameraRequesting: "正在请求摄像头权限...",
    cameraBinding: "正在绑定实时视频流...",
    cameraModelLoading: "正在加载本地手部模型...",
    cameraReady: "手势摄像头已连接。",
    cameraDenied: "摄像头权限已被拒绝。",
    cameraError: "当前无法启用摄像头手势追踪。",
    cameraInsecure: "必须在 localhost 或 HTTPS 下才能打开摄像头。",
    cameraPromptTimeout: "摄像头授权请求超时，请检查浏览器权限弹窗或设备占用情况。",
    cameraStreamTimeout: "摄像头已授权，但视频流未能按时启动。",
    cameraNoDevice: "浏览器当前未发现可用摄像头设备。",
    cameraBusy: "摄像头可能正被其他程序占用，或当前会话无法建立视频流。",
    enableCamera: "开启手势摄像头",
    retryCamera: "重试摄像头",
    handDetected: "手势锁定",
    fallbackMode: "鼠标兜底",
    permissionHint: "即使没有摄像头权限，页面也会继续响应鼠标交互。",
    permissionStateLabel: "权限",
    permissionPrompt: "等待授权",
    permissionGranted: "已授权",
    permissionDenied: "已拒绝",
    permissionUnsupported: "无 API",
    permissionUnknown: "未知",
    cameraRememberOn: "已记住自动启动摄像头。",
    cameraRememberOff: "摄像头将保持手动模式，直到你再次开启。",
    gestureIdle: "控制路由已就绪。",
    gestureOpenPalm: "张掌已扩展反应堆呼吸与外部场域。",
    gestureFist: "核心压缩已蓄力，松开即可释放。",
    gesturePoint: "聚焦电流已锁定目标走线。",
    gesturePeace: "双指电弧已稳定建立。",
    gesturePinch: "节点压缩正在焦点处形成。",
    gestureSwipe: "横向电流扫线已发射。",
    gestureCircle: "环形放电生成器已部署。",
    gestureThumbs: "身份确认脉冲已接受。",
    gestureBigBang: "奇点序列已启动。",
    gestureRotation: "旋腕已完成信号调频。",
    gesturePush: "前推动作已将数据包送入核心。",
    gestureSpread: "双手扩张已放大反应堆场域。",
  },
} satisfies Record<"en-US" | "zh-CN", Partial<SceneCopy>>;

function toNormalizedPoint(point: Point2D, width: number, height: number) {
  return {
    x: clamp01(point.x / width),
    y: clamp01(point.y / height),
  };
}

async function withTimeout<T>(promise: Promise<T>, timeoutMs: number, message: string) {
  let timer = 0;
  try {
    return await Promise.race([
      promise,
      new Promise<T>((_, reject) => {
        timer = window.setTimeout(() => reject(new Error(message)), timeoutMs);
      }),
    ]);
  } finally {
    if (timer) {
      window.clearTimeout(timer);
    }
  }
}

async function readCameraPermissionState(): Promise<CameraPermissionState> {
  if (!("permissions" in navigator) || typeof navigator.permissions?.query !== "function") {
    return "unsupported";
  }
  try {
    const result = await navigator.permissions.query({ name: "camera" as PermissionName });
    if (result.state === "granted" || result.state === "prompt" || result.state === "denied") {
      return result.state;
    }
    return "unknown";
  } catch {
    return "unsupported";
  }
}

async function waitForVideoReady(video: HTMLVideoElement, timeoutMs: number) {
  if (video.readyState >= HTMLMediaElement.HAVE_METADATA) {
    return;
  }

  await withTimeout(
    new Promise<void>((resolve, reject) => {
      const handleLoadedMetadata = () => {
        cleanup();
        resolve();
      };
      const handleError = () => {
        cleanup();
        reject(new Error("Video metadata failed to load"));
      };
      const cleanup = () => {
        video.removeEventListener("loadedmetadata", handleLoadedMetadata);
        video.removeEventListener("error", handleError);
      };

      video.addEventListener("loadedmetadata", handleLoadedMetadata, { once: true });
      video.addEventListener("error", handleError, { once: true });
    }),
    timeoutMs,
    "Video metadata timed out",
  );
}

async function requestCameraStream() {
  const attempts: MediaStreamConstraints[] = [
    {
      audio: false,
      video: {
        facingMode: "user",
        width: { ideal: 960 },
        height: { ideal: 720 },
        frameRate: { ideal: 30, max: 30 },
      },
    },
    { audio: false, video: true },
  ];

  let lastError: unknown = null;
  for (const constraints of attempts) {
    try {
      return await withTimeout(
        navigator.mediaDevices.getUserMedia(constraints),
        6500,
        "Camera permission timed out",
      );
    } catch (error) {
      lastError = error;
    }
  }

  throw lastError ?? new Error("Unable to acquire camera stream");
}

async function countVideoInputs() {
  if (!navigator.mediaDevices?.enumerateDevices) return null;
  try {
    const devices = await navigator.mediaDevices.enumerateDevices();
    return devices.filter((device) => device.kind === "videoinput").length;
  } catch {
    return null;
  }
}

export function ImmersiveLoginScene({
  entering = false,
  immersiveState = "normal",
  autoStartCamera = false,
  onAutoStartCameraChange,
  guideCollapsed = false,
  onToggleGuide,
  onTogglePassword,
  onToggleLocale,
  onClearField,
  onClearAll,
  onEnterImmersive,
  onExitImmersive,
  onSubmitGesture,
  formReady = false,
  reducedMotion = false,
}: ImmersiveLoginSceneProps) {
  const { locale } = useI18n();
  const copy = useMemo<SceneCopy>(() => {
    const baseCopy = HUD_COPY[locale] as SceneCopy;

    return locale === "zh-CN"
      ? {
          ...baseCopy,
          panelTitle: "反应堆总线在线",
          panelBody: "登录场景正在运行于一块活体电路板之上，每个手势都会把电流注入反应堆核心与走线网络。",
          panelHint: "张掌进入沉浸态，握拳返回登录，点赞用于身份确认。",
          metricSignal: "走线牵引",
          metricGrip: "核心握持",
          metricOpenness: "场域展开",
          metricArcLoad: "电弧负载",
          metricEkg: "核心 EKG",
          guideTitle: "控制映射",
          guideCollapse: "收起指南",
          guideExpand: "展开指南",
          guideOpenPalm: "张掌：扩大反应堆呼吸并点亮外环。",
          guideFist: "握拳：压缩核心并蓄力，松开后释放电弧。",
          guidePoint: "单指：向附近走线注入聚焦电流。",
          guidePeace: "V 手势：在两指之间保持稳定电弧。",
          guidePinch: "捏合：压缩局部节点簇并给核心增压。",
          guideSwipe: "横扫：沿整块电路板发射一次电流扫线。",
          guideCircle: "画圈：生成环形放电并向外扇出。",
          guideThumbs: "点赞：触发确认脉冲，准备好时提交登录。",
          guideBigBang: "双手张开：触发奇点蓄能和全场爆发。",
          guideRotation: "旋腕：调节信号场与脉冲节奏。",
          guidePush: "前推：向核心发射一组数据包。",
          guideSpread: "双手外拉：扩张反应堆场域和张力线。",
          collapseSignal: "收起信号面板",
          expandSignal: "展开信号面板",
          collapseCamera: "收起摄像头面板",
          expandCamera: "展开摄像头面板",
          cameraIdle: "摄像头待命中。",
          cameraLoading: "正在启动手势摄像头...",
          cameraRequesting: "正在请求摄像头权限...",
          cameraBinding: "正在绑定实时视频流...",
          cameraModelLoading: "正在加载本地手部模型...",
          cameraReady: "手势摄像头已连接。",
          cameraDenied: "摄像头权限已被拒绝。",
          cameraError: "当前无法启用摄像头手势追踪。",
          cameraInsecure: "必须在 localhost 或 HTTPS 下才能打开摄像头。",
          cameraPromptTimeout: "摄像头授权请求超时，请检查浏览器权限弹窗或设备占用情况。",
          cameraStreamTimeout: "摄像头已授权，但视频流未能按时启动。",
          cameraNoDevice: "浏览器当前未发现可用摄像头设备。",
          cameraBusy: "摄像头可能正在被其他程序占用，或当前会话无法建立视频流。",
          enableCamera: "开启手势摄像头",
          retryCamera: "重试摄像头",
          handDetected: "手势锁定",
          fallbackMode: "鼠标兜底",
          permissionHint: "即使没有摄像头权限，页面也会继续响应鼠标与键盘交互。",
          permissionStateLabel: "权限",
          permissionPrompt: "等待授权",
          permissionGranted: "已授权",
          permissionDenied: "已拒绝",
          permissionUnsupported: "无 API",
          permissionUnknown: "未知",
          cameraRememberOn: "已记住自动启动摄像头。",
          cameraRememberOff: "摄像头将保持手动模式，直到你再次开启。",
          gestureIdle: "控制路由已就绪。",
          gestureOpenPalm: "张掌已扩展反应堆呼吸与外部场域。",
          gestureFist: "核心压缩已蓄力，松开即可释放。",
          gesturePoint: "聚焦电流已锁定目标走线。",
          gesturePeace: "双指电弧已稳定建立。",
          gesturePinch: "节点压缩正在焦点处形成。",
          gestureSwipe: "横向电流扫线已发射。",
          gestureCircle: "环形放电生成器已部署。",
          gestureThumbs: "身份确认脉冲已接受。",
          gestureBigBang: "奇点序列已启动。",
          gestureRotation: "旋腕已完成信号调频。",
          gesturePush: "前推动作已将数据包送入核心。",
          gestureSpread: "双手扩张已放大反应堆场域。",
        }
      : baseCopy;
  }, [locale]);

  const rootRef = useRef<HTMLDivElement | null>(null);
  const pointerRef = useRef<Point2D>({ x: window.innerWidth / 2, y: window.innerHeight / 2 });
  const fieldRef = useRef({ x: 0.5, y: 0.5 });
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const previewCanvasRef = useRef<HTMLCanvasElement | null>(null);
  const gaussianCanvasRef = useRef<HTMLCanvasElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const landmarkerRef = useRef<HandLandmarker | null>(null);
  const splatSystemRef = useRef<ImmersiveSceneRenderer | null>(null);
  const detectionFrameRef = useRef<number | null>(null);
  const animationRef = useRef<number | null>(null);
  const layersRef = useRef<SceneLayers | null>(null);
  const cardAnchorRef = useRef<Point2D>({
    x: window.innerWidth / 2,
    y: window.innerHeight / 2,
  });
  const hostsRef = useRef<Record<string, HTMLDivElement | null>>({
    atmosphere: null,
    pcb: null,
    reactor: null,
    arcs: null,
  });
  const breathRef = useRef(getBreathController());
  const gestureControllerRef = useRef(new GestureController());
  const gestureFrameRef = useRef<GestureFrame>(createEmptyGestureFrame());
  const trajectoryRef = useRef<Array<{ point: Point2D; time: number }>>([]);
  const effectTimeoutsRef = useRef<number[]>([]);
  const disposedRef = useRef(false);
  const activeGestureRef = useRef<GestureFrame["type"]>("NONE");
  const lastTelemetryAtRef = useRef(0);
  const lastImmersiveExitAtRef = useRef(0);
  const randomArcAtRef = useRef(performance.now() + 2500);
  const submittingRef = useRef(false);
  const permissionStateRef = useRef<CameraPermissionState>("unknown");
  const comboHistoryRef = useRef<Array<{ gesture: string; time: number }>>([]);
  const pointerOrbitRef = useRef<{
    active: boolean;
    x: number;
    y: number;
  }>({
    active: false,
    x: 0,
    y: 0,
  });

  const [cameraState, setCameraState] = useState<CameraState>("idle");
  const [cameraStage, setCameraStage] = useState<CameraStage>("idle");
  const [cameraNote, setCameraNote] = useState(copy.cameraIdle);
  const [cameraErrorDetail, setCameraErrorDetail] = useState<string | null>(null);
  const [cameraPermissionState, setCameraPermissionState] = useState<CameraPermissionState>("unknown");
  const [gestureStatus, setGestureStatus] = useState(copy.gestureIdle);
  const [splatReady, setSplatReady] = useState(false);
  const [sceneList, setSceneList] = useState<BOSSceneSummary[]>([]);
  const [activeScene, setActiveScene] = useState<BOSSceneSummary | null>(null);
  const [sceneTransition, setSceneTransition] = useState<SceneTransitionKind | null>(null);
  const [transitionSnapshot, setTransitionSnapshot] = useState<string | null>(null);
  const [transitionDirection, setTransitionDirection] = useState<1 | -1>(1);
  const [annotationsVisible, setAnnotationsVisible] = useState(false);
  const [bookmarkedScenes, setBookmarkedScenes] = useState<string[]>([]);
  const [sceneFrozen, setSceneFrozen] = useState(false);
  const [rendererKind, setRendererKind] = useState<"procedural" | "gaussian" | null>(null);
  const [rendererQualityTier, setRendererQualityTier] = useState<"low" | "medium" | "high" | "ultra">("high");
  const [rendererFps, setRendererFps] = useState(60);
  const [signalPanelCollapsed, setSignalPanelCollapsed] = useState(false);
  const [cameraPanelCollapsed, setCameraPanelCollapsed] = useState(false);
  const [telemetry, setTelemetry] = useState<LoginSceneTelemetry>({
    signal: 36,
    grip: 12,
    openness: 38,
    energy: 24,
    arcLoad: 8,
    vortexLoad: 0,
    gestureLabel: copy.gestureIdle,
  });
  const [overlay, setOverlay] = useState({
    flash: 0,
    focus: { x: 0.5, y: 0.52 },
    energyBall: 0,
    confirmRing: false,
    waveDirection: 0 as -1 | 0 | 1,
    peaceArc: null as null | {
      from: Point2D;
      to: Point2D;
      intensity: number;
    },
    circlePulse: null as null | {
      center: Point2D;
      radius: number;
      clockwise: boolean;
    },
    rotationIndicator: null as null | {
      center: Point2D;
      delta: number;
      intensity: number;
    },
    pushBurst: [] as Array<{
      id: number;
      from: Point2D;
      to: Point2D;
      char: string;
      delay: number;
      duration: number;
    }>,
    pushBeam: null as null | {
      from: Point2D;
      to: Point2D;
      strength: number;
    },
    spreadLink: null as null | {
      left: Point2D;
      right: Point2D;
      strength: number;
    },
    spreadParticles: [] as Array<{
      id: number;
      t: number;
      offset: number;
      drift: number;
    }>,
    comboFlash: null as null | {
      label: string;
      startedAt: number;
    },
    singularity: 0,
    successWash: 0,
  });

  const guideItems = useMemo(
    () => [
      {
        icon: "spark" as const,
        text: copy.guideOpenPalm,
        preview: locale === "zh-CN" ? "场域扩张" : "Field expansion",
      },
      {
        icon: "zap" as const,
        text: copy.guideFist,
        preview: locale === "zh-CN" ? "引力坍缩" : "Gravity collapse",
      },
      {
        icon: "wave" as const,
        text: copy.guidePoint,
        preview: locale === "zh-CN" ? "牵引光束" : "Tractor beam",
      },
      {
        icon: "zap" as const,
        text: copy.guidePeace,
        preview: locale === "zh-CN" ? "双指持弧" : "Held arc",
      },
      {
        icon: "spark" as const,
        text: copy.guidePinch,
        preview: locale === "zh-CN" ? "压缩漩涡" : "Compression vortex",
      },
      {
        icon: "wave" as const,
        text: copy.guideSwipe,
        preview: locale === "zh-CN" ? "等离子横扫" : "Plasma sweep",
      },
      {
        icon: "spark" as const,
        text: copy.guideCircle,
        preview: locale === "zh-CN" ? "漩涡生成" : "Vortex generator",
      },
      {
        icon: "zap" as const,
        text: copy.guideThumbs,
        preview: locale === "zh-CN" ? "身份确认" : "Identity confirmation",
      },
      {
        icon: "wave" as const,
        text: copy.guideBigBang,
        preview: locale === "zh-CN" ? "奇点爆发" : "Singularity burst",
      },
      {
        icon: "spark" as const,
        text: copy.guideRotation,
        preview: locale === "zh-CN" ? "信号调频" : "Signal tuning",
      },
      {
        icon: "zap" as const,
        text: copy.guidePush,
        preview: locale === "zh-CN" ? "数据包突发" : "Data packet burst",
      },
      {
        icon: "wave" as const,
        text: copy.guideSpread,
        preview: locale === "zh-CN" ? "场域拉伸" : "Field stretch",
      },
    ],
    [copy, locale],
  );

  const permissionLabel =
    cameraPermissionState === "prompt"
      ? copy.permissionPrompt
      : cameraPermissionState === "granted"
        ? copy.permissionGranted
        : cameraPermissionState === "denied"
          ? copy.permissionDenied
          : cameraPermissionState === "unsupported"
            ? copy.permissionUnsupported
            : copy.permissionUnknown;

  const isImmersiveMode = immersiveState === "immersive";
  const isImmersiveVisible = immersiveState !== "normal";
  const canExitImmersive = immersiveState !== "normal" && immersiveState !== "exiting";
  const activeSceneIndex = activeScene ? sceneList.findIndex((scene) => scene.id === activeScene.id) : -1;
  const activeAnnotations = activeScene ? SCENE_ANNOTATIONS[activeScene.id] : null;
  const isActiveSceneBookmarked = activeScene ? bookmarkedScenes.includes(activeScene.id) : false;

  const emitGestureStatus = (message: string) => {
    setGestureStatus((current) => (current === message ? current : message));
    setTelemetry((current) =>
      current.gestureLabel === message ? current : { ...current, gestureLabel: message },
    );
  };

  const requestImmersiveExit = () => {
    if (!canExitImmersive) return false;
    const now = performance.now();
    if (now - lastImmersiveExitAtRef.current < 900) return false;
    lastImmersiveExitAtRef.current = now;
    triggerSceneTransition("shatter", () => {
      onExitImmersive?.();
    });
    emitGestureStatus(copy.gestureFist);
    return true;
  };

  const toggleAnnotations = () => {
    setAnnotationsVisible((current) => !current);
  };

  const toggleBookmarkForActiveScene = () => {
    if (!activeScene) return;
    setBookmarkedScenes((current) =>
      current.includes(activeScene.id)
        ? current.filter((sceneId) => sceneId !== activeScene.id)
        : [...current, activeScene.id],
    );
  };

  useEffect(() => {
    try {
      const stored = window.localStorage.getItem(BOOKMARK_STORAGE_KEY);
      if (!stored) return;
      const parsed = JSON.parse(stored);
      if (Array.isArray(parsed)) {
        setBookmarkedScenes(parsed.filter((value): value is string => typeof value === "string"));
      }
    } catch {
      // Ignore malformed persisted bookmark state.
    }
  }, []);

  useEffect(() => {
    try {
      window.localStorage.setItem(BOOKMARK_STORAGE_KEY, JSON.stringify(bookmarkedScenes));
    } catch {
      // Ignore persistence failures in privacy mode / locked storage.
    }
  }, [bookmarkedScenes]);

  const scheduleTimeout = (callback: () => void, delay: number) => {
    const timer = window.setTimeout(callback, delay);
    effectTimeoutsRef.current.push(timer);
    return timer;
  };

  const pushCombo = (gesture: string, center: Point2D) => {
    const now = Date.now();
    comboHistoryRef.current.push({ gesture, time: now });
    comboHistoryRef.current = comboHistoryRef.current.slice(-5);
    const layers = layersRef.current;
    if (!layers) return;

    for (const combo of COMBO_SEQUENCES) {
      const recent = comboHistoryRef.current.slice(-combo.sequence.length);
      if (recent.length !== combo.sequence.length) continue;
      const timeOk = now - recent[0].time < combo.window;
      const gestureOk = recent.every((entry, index) => entry.gesture === combo.sequence[index]);
      if (!timeOk || !gestureOk) continue;

      if (combo.label === "Neural Calibration") {
        layers.pcb.boostActivity(2.6, 1600);
        layers.atmosphere.expandField(1.25, 1400);
        setTelemetry((current) => ({
          ...current,
          signal: 42,
          grip: 18,
          openness: 46,
          arcLoad: 22,
        }));
      } else if (combo.label === "Lightning Storm") {
        layers.atmosphere.triggerLightningStorm(3000, 4);
      } else if (combo.label === "Vortex Big Bang") {
        layers.atmosphere.triggerLightningStorm(2200, 3);
        layers.reactor.bigExpand(1.18, 1500);
        layers.pcb.injectEnergy(center, 220, 1);
      }

      setOverlay((current) => ({
        ...current,
        comboFlash: { label: combo.label, startedAt: performance.now() },
      }));
      scheduleTimeout(() => {
        setOverlay((current) => ({ ...current, comboFlash: null }));
      }, 900);
      comboHistoryRef.current = [];
      break;
    }
  };

  const spawnPushBurst = (origin: Point2D, strength = 0.7) => {
    const target = { x: window.innerWidth / 2, y: window.innerHeight / 2 };
    const chars = ["0", "1", "#", "@", "*", "◇", "△", "◦"];
    const burst = Array.from({ length: 8 }, (_, index) => {
      const angle = (index / 8) * Math.PI * 2;
      const radius = 28 + Math.random() * 22;
      return {
        id: performance.now() + index,
        from: {
          x: origin.x + Math.cos(angle) * radius,
          y: origin.y + Math.sin(angle) * radius,
        },
        to: target,
        char: chars[index % chars.length] ?? "0",
        delay: index * 40,
        duration: 520 + strength * 320,
      };
    });
    setOverlay((current) => ({
      ...current,
      pushBurst: burst,
      pushBeam: { from: origin, to: target, strength },
    }));
    scheduleTimeout(() => {
      setOverlay((current) => ({ ...current, pushBurst: [], pushBeam: null }));
    }, 1200);
  };

  const createSpreadParticles = () =>
    Array.from({ length: 6 }, (_, index) => ({
      id: performance.now() + index,
      t: 0.12 + index * 0.14,
      offset: (Math.random() - 0.5) * 14,
      drift: Math.random() * 0.18 + 0.04,
    }));

  const triggerSceneTransition = (
    kind: SceneTransitionKind,
    action: () => void,
    directionOverride: 1 | -1 = transitionDirection,
  ) => {
    const profile = getSceneTransitionProfile(
      kind,
      activeScene?.id,
      directionOverride,
      overlay.focus,
      telemetry,
      gestureFrameRef.current.confidence,
      cameraState,
      immersiveState,
      reducedMotion,
    );
    const snapshot = splatSystemRef.current?.captureSnapshotDataUrl() ?? null;
    if (snapshot) {
      setTransitionSnapshot(snapshot);
    }
    setSceneTransition(kind);
    setOverlay((current) => ({ ...current, flash: 0.18 }));
    action();
    scheduleTimeout(() => {
      setSceneTransition(null);
      setTransitionSnapshot(null);
      setOverlay((current) => ({ ...current, flash: 0 }));
    }, profile.durationMs);
  };

  const jumpScene = (direction: 1 | -1, kind: SceneTransitionKind) => {
    const splat = splatSystemRef.current;
    if (!splat || sceneList.length === 0) return;
    setTransitionDirection(direction);
    triggerSceneTransition(kind, () => {
      const nextScene = splat.nextScene(direction);
      if (nextScene) {
        setActiveScene({
          id: nextScene.id,
          label: nextScene.label,
          labelEN: nextScene.labelEN,
          ambience: nextScene.ambience,
        });
      }
    }, direction);
  };

  const jumpSceneByAxis = (
    axis: "horizontal" | "vertical",
    direction: 1 | -1,
    kind: SceneTransitionKind,
  ) => {
    const splat = splatSystemRef.current;
    const targetId = getSceneNeighbor(activeScene?.id, axis, direction);
    if (!splat || !targetId) return;
    setTransitionDirection(direction);
    triggerSceneTransition(kind, () => {
      const nextScene = splat.loadScene(targetId);
      if (nextScene && typeof nextScene === "object") {
        const candidate = nextScene as {
          id: string;
          label: string;
          labelEN: string;
          ambience: string;
        };
        setActiveScene({
          id: candidate.id,
          label: candidate.label,
          labelEN: candidate.labelEN,
          ambience: candidate.ambience,
        });
      }
    }, direction);
  };

  const jumpToSceneIndex = (targetIndex: number, kind: SceneTransitionKind) => {
    const splat = splatSystemRef.current;
    if (!splat || sceneList.length === 0 || targetIndex < 0 || targetIndex >= sceneList.length) return;
    if (targetIndex === activeSceneIndex) return;

    const currentIndex = Math.max(0, activeSceneIndex);
    const direction: 1 | -1 = targetIndex > currentIndex ? 1 : -1;
    setTransitionDirection(direction);
    triggerSceneTransition(kind, () => {
      let scene = null;
      let cursor = currentIndex;
      while (cursor !== targetIndex) {
        cursor += direction;
        scene = splat.nextScene(direction);
      }
      if (scene) {
        setActiveScene({
          id: scene.id,
          label: scene.label,
          labelEN: scene.labelEN,
          ambience: scene.ambience,
        });
      }
    }, direction);
  };

  const drawPreview = (landmarksList: NormalizedLandmark[][]) => {
    const video = videoRef.current;
    const canvas = previewCanvasRef.current;
    if (!video || !canvas) return;
    const context = canvas.getContext("2d");
    if (!context) return;
    const width = video.videoWidth || 320;
    const height = video.videoHeight || 240;
    if (canvas.width !== width || canvas.height !== height) {
      canvas.width = width;
      canvas.height = height;
    }
    context.clearRect(0, 0, width, height);
    landmarksList.forEach((landmarks) => {
      context.strokeStyle = "rgba(131, 233, 255, 0.9)";
      context.lineWidth = 2;
      context.lineCap = "round";
      for (const [startIndex, endIndex] of HAND_CONNECTIONS) {
        const start = landmarks[startIndex];
        const end = landmarks[endIndex];
        if (!start || !end) continue;
        context.beginPath();
        context.moveTo((1 - start.x) * width, start.y * height);
        context.lineTo((1 - end.x) * width, end.y * height);
        context.stroke();
      }
      for (const landmark of landmarks) {
        context.beginPath();
        context.fillStyle = "rgba(220, 250, 255, 0.95)";
        context.arc((1 - landmark.x) * width, landmark.y * height, 3, 0, Math.PI * 2);
        context.fill();
      }
    });
  };

  const resolveHotspotAt = (point: Point2D) => {
    const shell = rootRef.current?.closest(".bos-auth-shell");
    if (!(shell instanceof HTMLElement)) return null;

    const targets = Array.from(shell.querySelectorAll<HTMLElement>("[data-login-target]"));
    let winner: string | null = null;
    let bestDistance = Number.POSITIVE_INFINITY;

    for (const target of targets) {
      const rect = target.getBoundingClientRect();
      const cx = rect.left + rect.width / 2;
      const cy = rect.top + rect.height / 2;
      const distance = Math.hypot(cx - point.x, cy - point.y);
      if (distance < bestDistance && distance < 120) {
        bestDistance = distance;
        winner = target.dataset.loginTarget ?? null;
      }
    }

    return winner;
  };

  const measureCardAnchor = () => {
    const shell = rootRef.current?.closest(".bos-auth-shell");
    const card = shell?.querySelector<HTMLElement>(".bos-auth-card");
    if (!card) {
      return {
        x: window.innerWidth / 2,
        y: window.innerHeight / 2,
      } satisfies Point2D;
    }

    const rect = card.getBoundingClientRect();
    return {
      x: rect.left + rect.width / 2,
      y: rect.top + rect.height / 2,
    } satisfies Point2D;
  };

  const handleGestureActivation = (type: GestureFrame["type"], frame: GestureFrame) => {
    const layers = layersRef.current;
    if (!layers) return;
    const center = frame.points.center ?? pointerRef.current;
    const splat = splatSystemRef.current;

    if (canExitImmersive && type === "INDEX_POINT") {
      requestImmersiveExit();
      return;
    }

    if (isImmersiveMode) {
      switch (type) {
        case "SWIPE":
          jumpSceneByAxis(
            "horizontal",
            frame.params.swipeDirection < 0 ? -1 : 1,
            frame.params.swipeDirection < 0 ? "page-left" : "page-right",
          );
          emitGestureStatus(`${copy.gestureSwipe} ${frame.params.swipeDirection < 0 ? "PREV" : "NEXT"}`);
          return;
        case "SWIPE_UP":
          jumpSceneByAxis("vertical", 1, "dive");
          emitGestureStatus(`${copy.gestureSwipe} DEPTH+`);
          return;
        case "SWIPE_DOWN":
          jumpSceneByAxis("vertical", -1, "shatter");
          emitGestureStatus(`${copy.gestureSwipe} DEPTH-`);
          return;
        case "HAND_PUSH":
          splat?.setChargeState(Math.min(1.2, 0.55 + frame.params.pushStrength));
          splat?.triggerPulse("burst");
          splat?.zoomCamera(1 + frame.params.pushStrength * 1.6);
          emitGestureStatus(copy.gesturePush);
          return;
        case "HAND_PULL":
          splat?.setChargeState(0.24);
          splat?.zoomCamera(-(1 + frame.params.pushStrength * 1.2));
          emitGestureStatus(`${copy.gesturePush} BACK`);
          return;
        case "WRIST_ROTATION":
          splat?.setGestureFocus("rotation");
          splat?.orbitCamera(frame.params.rotationDelta * 120, 0);
          emitGestureStatus(copy.gestureRotation);
          return;
        case "TWO_HANDS_PINCH_APART":
          splat?.setChargeState(0.82);
          splat?.triggerPulse("confirm");
          jumpScene(1, "portal");
          emitGestureStatus(copy.gestureSpread);
          return;
        case "OPEN_PALM":
          splat?.freezeField(true);
          splat?.setGestureFocus("open_palm");
          splat?.setAutoFloatEnabled(false);
          setSceneFrozen(true);
          emitGestureStatus(copy.gestureOpenPalm);
          return;
        case "INDEX_POINT":
          requestImmersiveExit();
          return;
        case "PEACE_SIGN":
          splat?.setGestureFocus("annotations");
          toggleAnnotations();
          emitGestureStatus(copy.gesturePeace);
          return;
        case "THUMBS_UP":
          splat?.setChargeState(1);
          splat?.triggerPulse("success");
          toggleBookmarkForActiveScene();
          setOverlay((current) => ({
            ...current,
            confirmRing: true,
            successWash: 1,
          }));
          scheduleTimeout(() => {
            setOverlay((current) => ({ ...current, confirmRing: false, successWash: 0 }));
          }, 720);
          emitGestureStatus(copy.gestureThumbs);
          return;
        default:
          return;
      }
    }

    if (type !== "NONE") {
      pushCombo(type === "SWIPE" ? (frame.params.swipeDirection < 0 ? "SWIPE_LEFT" : "SWIPE_RIGHT") : type, center);
    }

    switch (type) {
      case "SWIPE": {
        const direction = frame.params.swipeDirection === 0 ? 1 : frame.params.swipeDirection;
        layers.atmosphere.expandField(1.14, 500);
        layers.pcb.triggerSweep(center, direction);
        layers.reactor.bigExpand(1.08, 520);
        const hotspot = resolveHotspotAt(center);
        if (hotspot === "username" || hotspot === "password") {
          onClearField?.(hotspot);
        } else {
          onClearAll?.();
        }
        setOverlay((current) => ({ ...current, waveDirection: direction }));
        emitGestureStatus(copy.gestureSwipe);
        scheduleTimeout(() => {
          setOverlay((current) => ({ ...current, waveDirection: 0 }));
        }, 420);
        break;
      }
      case "CIRCLE":
        layers.atmosphere.expandField(1.12, 1100);
        layers.atmosphere.accelerateStreams(1.8, 1800);
        layers.pcb.injectEnergy(center, 180, 1);
        layers.pcb.boostActivity(2.4, 1400);
        layers.reactor.bigExpand(1.14, 1200);
        for (let angle = 0; angle < Math.PI * 2; angle += Math.PI / 3) {
          layers.arcs.spawnRadial(center, angle);
        }
        setOverlay((current) => ({
          ...current,
          circlePulse: {
            center,
            radius: 220,
            clockwise: frame.params.clockwise,
          },
        }));
        scheduleTimeout(() => {
          setOverlay((current) => ({ ...current, circlePulse: null }));
        }, 2200);
        emitGestureStatus(copy.gestureCircle);
        break;
      case "THUMBS_UP":
        layers.atmosphere.accelerateStreams(1.8, 1200);
        setOverlay((current) => ({
          ...current,
          confirmRing: true,
          focus: toNormalizedPoint(center, window.innerWidth, window.innerHeight),
          successWash: 1,
        }));
        layers.reactor.triggerConfirmPulse();
        layers.reactor.triggerSuccess();
        layers.pcb.boostActivity(2.2, 1100);
        breathRef.current.setColor("#00FF9D");
        emitGestureStatus(copy.gestureThumbs);
        scheduleTimeout(() => {
          setOverlay((current) => ({ ...current, confirmRing: false, successWash: 0 }));
        }, 850);
        if (formReady && !submittingRef.current) {
          submittingRef.current = true;
          scheduleTimeout(() => {
            onSubmitGesture?.();
            submittingRef.current = false;
          }, 800);
        }
        break;
      case "BOTH_HANDS_OPEN":
        breathRef.current.pause();
        layers.atmosphere.triggerLightningStorm(2600, 3);
        layers.atmosphere.accelerateStreams(3.2, 2000);
        layers.atmosphere.expandField(1.35, 1800);
        layers.pcb.boostActivity(3.1, 1800);
        layers.pcb.injectEnergy(center, 240, 1);
        layers.reactor.setCompression(1);
        setOverlay((current) => ({
          ...current,
          singularity: 1,
          focus: toNormalizedPoint(center, window.innerWidth, window.innerHeight),
        }));
        emitGestureStatus(copy.gestureBigBang);
        scheduleTimeout(() => {
          setOverlay((current) => ({ ...current, flash: 0.16 }));
        }, 220);
        scheduleTimeout(() => {
          setOverlay((current) => ({ ...current, flash: 0, singularity: 0 }));
          layers.reactor.setCompression(0);
          layers.reactor.bigExpand(1.24, 1600);
          layers.pcb.boostActivity(3.2, 1800);
          layers.pcb.injectEnergy(center, 260, 1);
          for (let index = 0; index < 10; index += 1) {
            layers.arcs.spawnRadial(center, (index / 10) * Math.PI * 2);
          }
          breathRef.current.resume();
        }, 520);
        break;
      case "OPEN_PALM":
        layers.atmosphere.expandField(1.4, 1600);
        layers.atmosphere.accelerateStreams(3, 2000);
        layers.atmosphere.pulseClouds(center, 1.8);
        onEnterImmersive?.();
        emitGestureStatus(copy.gestureOpenPalm);
        break;
      case "FIST":
        layers.atmosphere.setMagneticFocus(center, 0.8);
        emitGestureStatus(copy.gestureFist);
        break;
      case "INDEX_POINT":
        layers.atmosphere.setMagneticFocus(frame.points.indexTip ?? center, 0.6);
        emitGestureStatus(copy.gesturePoint);
        break;
      case "PEACE_SIGN":
        if (resolveHotspotAt(center) === "toggle-locale") {
          onToggleLocale?.();
        }
        emitGestureStatus(copy.gesturePeace);
        break;
      case "PINCH":
        layers.atmosphere.setMagneticFocus(frame.points.pinchCenter ?? center, 0.8);
        if (resolveHotspotAt(center) === "toggle-password") {
          onTogglePassword?.();
        }
        emitGestureStatus(copy.gesturePinch);
        break;
      case "WRIST_ROTATION":
        layers.atmosphere.accelerateStreams(1.2 + Math.min(1, Math.abs(frame.params.rotationDelta) * 4), 420);
        setTelemetry((current) => ({
          ...current,
          signal: Math.max(0, Math.min(100, current.signal + Math.round(frame.params.rotationDelta * 40))),
        }));
        setOverlay((current) => ({
          ...current,
          rotationIndicator: {
            center,
            delta: frame.params.rotationDelta,
            intensity: Math.min(1, Math.abs(frame.params.rotationDelta) * 6),
          },
        }));
        scheduleTimeout(() => {
          setOverlay((current) => ({ ...current, rotationIndicator: null }));
        }, 260);
        emitGestureStatus(copy.gestureRotation);
        break;
      case "HAND_PUSH":
        layers.pcb.boostActivity(2 + frame.params.pushStrength, 900);
        layers.atmosphere.accelerateStreams(2.5, 900);
        layers.reactor.triggerConfirmPulse(600);
        spawnPushBurst(center, frame.params.pushStrength);
        setOverlay((current) => ({ ...current, flash: 0.08 }));
        scheduleTimeout(() => {
          setOverlay((current) => ({ ...current, flash: 0 }));
        }, 220);
        emitGestureStatus(copy.gesturePush);
        break;
      case "TWO_HANDS_PINCH_APART":
        layers.atmosphere.expandField(1.2 + (frame.params.spreadScale - 0.5) * 0.6, 800);
        layers.reactor.bigExpand(1 + (frame.params.spreadScale - 0.5) * 0.28, 900);
        if (frame.points.leftHand && frame.points.rightHand) {
          setOverlay((current) => ({
            ...current,
            spreadLink: {
              left: frame.points.leftHand!,
              right: frame.points.rightHand!,
              strength: Math.max(0, frame.params.spreadScale - 0.5),
            },
            spreadParticles: createSpreadParticles(),
          }));
        }
        emitGestureStatus(copy.gestureSpread);
        break;
      default:
        break;
    }
  };

  const handleGestureRelease = (previous: GestureFrame["type"], frame: GestureFrame) => {
    const layers = layersRef.current;
    if (!layers) return;
    const center = frame.points.center ?? pointerRef.current;
    layers.atmosphere.setMagneticFocus(null, 0);

    if (isImmersiveMode && previous === "OPEN_PALM") {
      splatSystemRef.current?.freezeField(false);
      splatSystemRef.current?.setGestureFocus(null);
      splatSystemRef.current?.setAutoFloatEnabled(true);
      setSceneFrozen(false);
      return;
    }

    switch (previous) {
      case "FIST":
        layers.atmosphere.pulseClouds(center, 3.2);
        layers.reactor.setCompression(0);
        layers.reactor.bigExpand(1.18, 760);
        layers.pcb.boostActivity(2.8, 1000);
        layers.pcb.injectEnergy(center, 180, 1);
        for (let index = 0; index < 5; index += 1) {
          layers.arcs.spawnFromPoint(center, { delay: index * 80 });
        }
        breathRef.current.resume();
        breathRef.current.setPeriod(4000);
        setOverlay((current) => ({ ...current, energyBall: 0 }));
        break;
      case "PEACE_SIGN":
        layers.arcs.releaseHeldArc();
        break;
      case "PINCH":
        layers.atmosphere.expandField(1.08, 700);
        layers.pcb.injectEnergy(center, 120, 1);
        layers.arcs.spawnFromPoint(center);
        break;
      default:
        break;
    }
  };

  const applyGestureEffects = () => {
    const layers = layersRef.current;
    if (!layers) return;

    const frame = gestureFrameRef.current;
    const cardAnchor = measureCardAnchor();
    cardAnchorRef.current = cardAnchor;
    const focus =
      frame.points.pinchCenter ??
      frame.points.indexTip ??
      frame.points.center ??
      pointerRef.current;
    const normalizedFocus = toNormalizedPoint(focus, window.innerWidth, window.innerHeight);
    splatSystemRef.current?.setFieldAttractor(
      normalizedFocus.x * 2 - 1,
      (1 - normalizedFocus.y) * 2 - 1,
      frame.confidence,
    );
    splatSystemRef.current?.setTrackingConfidence(frame.confidence);
    const normalizedCardAnchor = toNormalizedPoint(
      cardAnchor,
      window.innerWidth,
      window.innerHeight,
    );
    if (rootRef.current) {
      rootRef.current.style.setProperty("--breath-anchor-x", `${normalizedCardAnchor.x * 100}%`);
      rootRef.current.style.setProperty("--breath-anchor-y", `${normalizedCardAnchor.y * 100}%`);
    }
    setOverlay((current) => ({
      ...current,
      focus: normalizedFocus,
      energyBall:
        frame.type === "FIST" ? Math.min(1, current.energyBall + 0.04) : current.energyBall * 0.9,
      peaceArc:
        frame.type === "PEACE_SIGN" && frame.points.indexTip && frame.points.middleTip
          ? {
              from: frame.points.indexTip,
              to: frame.points.middleTip,
              intensity: frame.confidence,
            }
          : null,
      successWash:
        current.successWash > 0 && frame.type !== "THUMBS_UP"
          ? Math.max(0, current.successWash - 0.03)
          : current.successWash,
      singularity:
        current.singularity > 0 && frame.type !== "BOTH_HANDS_OPEN"
          ? Math.max(0, current.singularity - 0.05)
          : current.singularity,
      rotationIndicator:
        frame.type === "WRIST_ROTATION"
          ? {
              center: focus,
              delta: frame.params.rotationDelta,
              intensity: Math.min(1, Math.abs(frame.params.rotationDelta) * 6),
            }
          : current.rotationIndicator,
      spreadLink:
        frame.type === "TWO_HANDS_PINCH_APART" && frame.points.leftHand && frame.points.rightHand
          ? {
              left: frame.points.leftHand,
              right: frame.points.rightHand,
              strength: Math.max(0, frame.params.spreadScale - 0.5),
            }
          : frame.type !== "TWO_HANDS_PINCH_APART"
            ? null
            : current.spreadLink,
      spreadParticles:
        frame.type === "TWO_HANDS_PINCH_APART"
          ? current.spreadParticles.map((particle) => ({
              ...particle,
              t: (particle.t + particle.drift) % 1,
            }))
          : [],
    }));

    layers.atmosphere.setPointer(focus);
    layers.reactor.setFocus({ x: 0.5, y: 0.5 });
    layers.reactor.setExpansion(0);
    if (frame.type !== "FIST") {
      layers.reactor.setCompression(0);
    }

    if (frame.type !== "THUMBS_UP" && activeGestureRef.current !== "THUMBS_UP") {
      breathRef.current.setColor("#00C8D4");
    }
    if (frame.type !== "OPEN_PALM") {
      breathRef.current.setPeriod(4000);
    }

    if (isImmersiveMode) {
      if (frame.type === "INDEX_POINT" && frame.confidence > 0.72) {
        requestImmersiveExit();
      }
      if (frame.type === "WRIST_ROTATION") {
        splatSystemRef.current?.orbitCamera(frame.params.rotationDelta * 24, 0);
      }
      if (frame.type === "HAND_PUSH") {
        splatSystemRef.current?.zoomCamera(0.04 + frame.params.pushStrength * 0.08);
      }
      if (frame.type === "HAND_PULL") {
        splatSystemRef.current?.zoomCamera(-(0.04 + frame.params.pushStrength * 0.08));
      }
    } else {
      switch (frame.type) {
        case "OPEN_PALM":
          breathRef.current.setPeriod(2500);
          layers.reactor.setExpansion(frame.confidence);
          layers.pcb.boostActivity(1.8 + frame.confidence, 180);
          layers.atmosphere.expandField(1.4, 900);
          break;
        case "FIST":
          breathRef.current.setPeriod(7000);
          breathRef.current.pause();
          layers.reactor.setCompression(frame.confidence);
          layers.pcb.boostActivity(1.2, 180);
          layers.atmosphere.setMagneticFocus(focus, frame.confidence);
          break;
        case "INDEX_POINT":
          layers.pcb.injectEnergy(frame.points.indexTip ?? focus, 80, 0.7);
          layers.atmosphere.setMagneticFocus(frame.points.indexTip ?? focus, 0.5);
          break;
        case "PEACE_SIGN":
          if (frame.points.indexTip && frame.points.middleTip) {
            layers.arcs.holdArc(frame.points.indexTip, frame.points.middleTip);
          }
          break;
        case "PINCH":
          layers.reactor.setCompression(frame.confidence * 0.75);
          layers.pcb.injectEnergy(frame.points.pinchCenter ?? focus, 64, 0.9);
          layers.atmosphere.setMagneticFocus(frame.points.pinchCenter ?? focus, 0.75);
          break;
        case "THUMBS_UP":
          breathRef.current.setColor("#00FF9D");
          break;
        case "WRIST_ROTATION":
          layers.atmosphere.accelerateStreams(1.1 + Math.min(1, Math.abs(frame.params.rotationDelta) * 5), 180);
          break;
        case "HAND_PUSH":
          layers.atmosphere.accelerateStreams(1.8 + frame.params.pushStrength, 320);
          layers.pcb.boostActivity(1.8, 240);
          break;
        case "TWO_HANDS_PINCH_APART":
          layers.reactor.setExpansion(Math.max(0, frame.params.spreadScale - 0.5));
          layers.atmosphere.expandField(1 + Math.max(0, frame.params.spreadScale - 0.5) * 0.6, 260);
          break;
        default:
          break;
      }

      if (frame.type !== "PEACE_SIGN") {
        layers.arcs.releaseHeldArc();
      }
    }

    if (activeGestureRef.current !== frame.type) {
      if (activeGestureRef.current !== "NONE") {
        handleGestureRelease(activeGestureRef.current, frame);
      }
      if (frame.type !== "NONE") {
        handleGestureActivation(frame.type, frame);
      } else {
        setGestureStatus(copy.gestureIdle);
      }
      activeGestureRef.current = frame.type;
    }
  };

  const runDetectionLoop = () => {
    const video = videoRef.current;
    const landmarker = landmarkerRef.current;
    if (!video || !landmarker || disposedRef.current) return;

    const detect = (timestamp: number) => {
      if (disposedRef.current) return;
      if (video.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA) {
        const result = landmarker.detectForVideo(video, performance.now());
        const landmarks = result.landmarks ?? [];
        drawPreview(landmarks);
        const width = window.innerWidth;
        const height = window.innerHeight;
        const center =
          landmarks[0]?.[9]
            ? { x: (1 - landmarks[0][9].x) * width, y: landmarks[0][9].y * height }
            : pointerRef.current;
        trajectoryRef.current.push({ point: center, time: timestamp });
        trajectoryRef.current = trajectoryRef.current.filter((entry) => timestamp - entry.time <= 900);

        const candidate = detectGestureCandidate({
          landmarks,
          width,
          height,
          now: timestamp,
          trajectory: trajectoryRef.current,
        });

        gestureFrameRef.current = gestureControllerRef.current.update(
          candidate.type === "NONE"
            ? null
            : {
                type: candidate.type,
                confidence: candidate.confidence,
                points: candidate.points,
                swipeDirection: candidate.swipeDirection,
                clockwise: candidate.clockwise,
                rotationDelta: candidate.rotationDelta,
                pushStrength: candidate.pushStrength,
                spreadScale: candidate.spreadScale,
              },
          timestamp,
        );

        if (timestamp - lastTelemetryAtRef.current > 80) {
          lastTelemetryAtRef.current = timestamp;
          setTelemetry((current) => ({
            signal: Math.round((candidate.metrics?.openness ?? 0.36) * 100),
            grip: Math.round((candidate.metrics?.grip ?? 0.12) * 100),
            openness: Math.round((candidate.metrics?.openness ?? 0.38) * 100),
            energy: Math.round(gestureFrameRef.current.confidence * 100),
            arcLoad: Math.round(
              Math.min(
                100,
                (gestureFrameRef.current.confidence +
                  (candidate.type === "PEACE_SIGN" ? 0.35 : 0.08)) *
                  100,
              ),
            ),
            vortexLoad:
              candidate.type === "CIRCLE" || candidate.type === "PINCH"
                ? 100
                : current.vortexLoad * 0.8,
            gestureLabel: current.gestureLabel,
          }));
        }
      }

      detectionFrameRef.current = window.requestAnimationFrame(detect);
    };

    detectionFrameRef.current = window.requestAnimationFrame(detect);
  };

  const startCamera = async () => {
    if (cameraState === "loading") return;

    try {
      if (!window.isSecureContext) {
        setCameraStage("idle");
        setCameraErrorDetail(copy.cameraInsecure);
        setCameraState("error");
        return;
      }

      setCameraErrorDetail(null);
      setCameraState("loading");
      setCameraStage("requesting");
      const initialPermissionState = await readCameraPermissionState();
      permissionStateRef.current = initialPermissionState;
      setCameraPermissionState(initialPermissionState);

      if (!navigator.mediaDevices?.getUserMedia) {
        throw new Error("media unsupported");
      }

      const videoInputCount = await countVideoInputs();
      if (videoInputCount === 0) {
        setCameraStage("idle");
        setCameraErrorDetail(copy.cameraNoDevice);
        setCameraState("error");
        return;
      }

      const stream = await requestCameraStream();
      if (disposedRef.current) {
        stream.getTracks().forEach((track) => track.stop());
        return;
      }

      streamRef.current?.getTracks().forEach((track) => track.stop());
      streamRef.current = stream;
      onAutoStartCameraChange?.(true);
      setCameraPermissionState("granted");

      const video = videoRef.current;
      if (!video) throw new Error("Camera preview element unavailable");
      setCameraStage("binding");
      video.srcObject = stream;
      await waitForVideoReady(video, 5000);
      await withTimeout(video.play(), 5000, "Camera playback timed out");

      const vision = await import("@mediapipe/tasks-vision");
      setCameraStage("model");
      const fileset = await withTimeout(
        vision.FilesetResolver.forVisionTasks(CAMERA_WASM_BASE),
        8000,
        "Local MediaPipe runtime timed out",
      );
      const handLandmarker = await withTimeout(
        vision.HandLandmarker.createFromOptions(fileset, {
          baseOptions: {
            modelAssetPath: HAND_MODEL_ASSET,
          },
          runningMode: "VIDEO",
          numHands: 2,
          minHandDetectionConfidence: 0.58,
          minHandPresenceConfidence: 0.56,
          minTrackingConfidence: 0.52,
        }),
        10_000,
        "Local hand model timed out",
      );

      if (disposedRef.current) {
        handLandmarker.close();
        return;
      }

      landmarkerRef.current?.close();
      landmarkerRef.current = handLandmarker;
      if (detectionFrameRef.current != null) {
        window.cancelAnimationFrame(detectionFrameRef.current);
      }
      runDetectionLoop();
      setCameraStage("idle");
      setCameraState("ready");
    } catch (error) {
      streamRef.current?.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
      const errorName = error instanceof DOMException ? error.name : "";
      if (errorName === "NotAllowedError" || errorName === "SecurityError") {
        setCameraStage("idle");
        setCameraErrorDetail(null);
        setCameraPermissionState("denied");
        setCameraState("denied");
        onAutoStartCameraChange?.(false);
      } else if (error instanceof Error && /timed out/i.test(error.message)) {
        setCameraStage("idle");
        setCameraPermissionState(permissionStateRef.current === "granted" ? "granted" : "prompt");
        setCameraErrorDetail(
          permissionStateRef.current === "granted"
            ? copy.cameraStreamTimeout
            : copy.cameraPromptTimeout,
        );
        setCameraState("error");
      } else if (
        error instanceof DOMException &&
        (error.name === "NotReadableError" || error.name === "AbortError")
      ) {
        setCameraStage("idle");
        permissionStateRef.current = "granted";
        setCameraPermissionState("granted");
        setCameraErrorDetail(copy.cameraBusy);
        setCameraState("error");
      } else {
        setCameraStage("idle");
        setCameraState("error");
        setCameraErrorDetail(
          error instanceof Error && error.message
            ? `${copy.cameraError} ${error.message}`
            : copy.cameraError,
        );
      }
    }
  };

  useEffect(() => {
    const nextNote =
      cameraState === "idle"
        ? copy.cameraIdle
        : cameraState === "loading"
          ? cameraStage === "requesting"
            ? copy.cameraRequesting
            : cameraStage === "binding"
              ? copy.cameraBinding
              : cameraStage === "model"
                ? copy.cameraModelLoading
                : copy.cameraLoading
          : cameraState === "ready"
            ? copy.cameraReady
            : cameraState === "denied"
              ? copy.cameraDenied
              : cameraErrorDetail ?? copy.cameraError;
    setCameraNote((current) => (current === nextNote ? current : nextNote));
  }, [cameraErrorDetail, cameraStage, cameraState, copy]);

  useEffect(() => {
    const nextGestureIdle = copy.gestureIdle;
    setGestureStatus((current) => (current === nextGestureIdle ? current : nextGestureIdle));
    setTelemetry((current) =>
      current.gestureLabel === nextGestureIdle ? current : { ...current, gestureLabel: nextGestureIdle },
    );
  }, [copy.gestureIdle]);

  useEffect(() => {
    const canvas = gaussianCanvasRef.current;
    if (!canvas) return;

    let cancelled = false;
    let cleanup: (() => void) | null = null;

    const setupRenderer = async () => {
    try {
      const splat = await createSceneRenderer(canvas, {
        particleCount: 16000,
        autoFloat: true,
        mode: import.meta.env.VITE_SCENE_RENDERER_MODE ?? "auto",
      });
      if (cancelled) {
        splat.dispose();
        return;
      }
      splatSystemRef.current = splat;
      setRendererKind(splat.kind);
      setRendererQualityTier(splat.getQualityTier());
      setRendererFps(splat.getStats().fps);
      const handleResize = () => splat.resize();

      const handleReady = () => {
        setSplatReady(true);
        const scenes = splat.getSceneList();
        setSceneList(scenes);
        setActiveScene(splat.getCurrentSceneInfo());
      };
      const handleSceneChange = (event: Event) => {
        const detail = (event as CustomEvent<BOSSceneSummary>).detail;
        setActiveScene(detail);
      };

      splat.addEventListener("scenesready", handleReady);
      splat.addEventListener("scenechange", handleSceneChange);
      window.addEventListener("resize", handleResize);

      cleanup = () => {
        splat.removeEventListener("scenesready", handleReady);
        splat.removeEventListener("scenechange", handleSceneChange);
        window.removeEventListener("resize", handleResize);
        splat.dispose();
        if (splatSystemRef.current === splat) {
          splatSystemRef.current = null;
        }
      };
    } catch (error) {
      console.warn("[BOS] Procedural splat fallback failed, keeping classic background.", error);
      setSplatReady(false);
      setRendererKind(null);
    }
    };

    void setupRenderer();

    return () => {
      cancelled = true;
      cleanup?.();
    };
  }, []);

  useEffect(() => {
    const splat = splatSystemRef.current;
    if (!splat) return;
    if (isImmersiveVisible) {
      splat.start();
    } else {
      splat.stop();
    }
  }, [isImmersiveVisible]);

  useEffect(() => {
    const timer = window.setInterval(() => {
      const renderer = splatSystemRef.current;
      if (!renderer) return;
      const stats = renderer.getStats();
      setRendererQualityTier(stats.qualityTier);
      setRendererFps(stats.fps);
    }, 800);

    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    if (!isImmersiveVisible) {
      setAnnotationsVisible(false);
      setSceneFrozen(false);
      splatSystemRef.current?.setAutoFloatEnabled(true);
    }
  }, [isImmersiveVisible]);

  useEffect(() => {
    if (!isImmersiveVisible) return;

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onExitImmersive?.();
        return;
      }
      if (event.key === "ArrowLeft") {
        event.preventDefault();
        jumpScene(-1, "page-left");
        return;
      }
      if (event.key === "ArrowRight") {
        event.preventDefault();
        jumpScene(1, "page-right");
        return;
      }
      if (event.key === "ArrowUp") {
        event.preventDefault();
        jumpScene(1, "portal");
        return;
      }
      if (event.key === "ArrowDown") {
        event.preventDefault();
        jumpScene(-1, "shatter");
        return;
      }
      if (event.key === "+" || event.key === "=") {
        event.preventDefault();
        splatSystemRef.current?.zoomCamera(0.6);
        return;
      }
      if (event.key === "-" || event.key === "_") {
        event.preventDefault();
        splatSystemRef.current?.zoomCamera(-0.6);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isImmersiveVisible, onExitImmersive]);

  useEffect(() => {
    const canvas = gaussianCanvasRef.current;
    if (!canvas || !isImmersiveVisible) return;

    const handlePointerDown = (event: PointerEvent) => {
      pointerOrbitRef.current = {
        active: true,
        x: event.clientX,
        y: event.clientY,
      };
      canvas.setPointerCapture?.(event.pointerId);
    };

    const handlePointerMove = (event: PointerEvent) => {
      if (!pointerOrbitRef.current.active) return;
      const dx = event.clientX - pointerOrbitRef.current.x;
      const dy = event.clientY - pointerOrbitRef.current.y;
      pointerOrbitRef.current.x = event.clientX;
      pointerOrbitRef.current.y = event.clientY;
      splatSystemRef.current?.orbitCamera(dx, dy);
    };

    const handlePointerUp = (event: PointerEvent) => {
      pointerOrbitRef.current.active = false;
      canvas.releasePointerCapture?.(event.pointerId);
    };

    const handleWheel = (event: WheelEvent) => {
      event.preventDefault();
      splatSystemRef.current?.zoomCamera(event.deltaY < 0 ? 0.8 : -0.8);
    };

    canvas.addEventListener("pointerdown", handlePointerDown);
    canvas.addEventListener("pointermove", handlePointerMove);
    canvas.addEventListener("pointerup", handlePointerUp);
    canvas.addEventListener("pointerleave", handlePointerUp);
    canvas.addEventListener("wheel", handleWheel, { passive: false });

    return () => {
      canvas.removeEventListener("pointerdown", handlePointerDown);
      canvas.removeEventListener("pointermove", handlePointerMove);
      canvas.removeEventListener("pointerup", handlePointerUp);
      canvas.removeEventListener("pointerleave", handlePointerUp);
      canvas.removeEventListener("wheel", handleWheel);
      pointerOrbitRef.current.active = false;
    };
  }, [isImmersiveVisible]);

  useEffect(() => {
    const handlePointerMove = (event: PointerEvent) => {
      pointerRef.current = { x: event.clientX, y: event.clientY };
    };
    window.addEventListener("pointermove", handlePointerMove);
    return () => window.removeEventListener("pointermove", handlePointerMove);
  }, []);

  useEffect(() => {
    const root = rootRef.current;
    if (!root) return;

    const layers: SceneLayers = {
      atmosphere: new AtmosphereLayer(),
      pcb: new PCBTraceLayer(),
      reactor: new ReactorCoreLayer(),
      arcs: new ElectricArcsLayer(),
    };
    layersRef.current = layers;
    layers.atmosphere.mount(hostsRef.current.atmosphere!);
    layers.pcb.mount(hostsRef.current.pcb!);
    layers.reactor.mount(hostsRef.current.reactor!);
    layers.arcs.mount(hostsRef.current.arcs!);

    const resize = () => {
      const width = window.innerWidth;
      const height = window.innerHeight;
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      Object.values(layers).forEach((layer) => layer.resize(width, height, dpr));
    };

    resize();
    window.addEventListener("resize", resize);

    let last = performance.now();
    const tick = (now: number) => {
      if (disposedRef.current) return;
      const dt = now - last;
      last = now;

      const input = gestureFrameRef.current.points.center ?? pointerRef.current;
      fieldRef.current.x = lerp(fieldRef.current.x, clamp01(input.x / window.innerWidth), 0.08);
      fieldRef.current.y = lerp(fieldRef.current.y, clamp01(input.y / window.innerHeight), 0.08);
      cardAnchorRef.current = measureCardAnchor();
      layers.atmosphere.setPointer(input);

       applyGestureEffects();
       breathRef.current.update(dt);
       splatSystemRef.current?.setBreathPhase(breathRef.current.phase);
       Object.values(layers).forEach((layer) => layer.update(dt, now));

      if (now > randomArcAtRef.current) {
        const anchor = {
          x: window.innerWidth / 2,
          y: window.innerHeight / 2,
        };
        const baseRadius = Math.min(window.innerWidth, window.innerHeight) * 0.38;
        const armAngles = [270, 30, 150].map((degrees) => (degrees * Math.PI) / 180);
        const fromArm = armAngles[Math.floor(Math.random() * armAngles.length)] ?? armAngles[0];
        const toAngle = fromArm + (Math.random() - 0.5) * Math.PI * 0.85;
        const from = {
          x: anchor.x + Math.cos(fromArm) * baseRadius * 0.72,
          y: anchor.y + Math.sin(fromArm) * baseRadius * 0.72,
        };
        const to = {
          x: anchor.x + Math.cos(toAngle) * randomBetween(baseRadius * 1.15, baseRadius * 2.1),
          y: anchor.y + Math.sin(toAngle) * randomBetween(baseRadius * 1.15, baseRadius * 2.1),
        };
        layers.arcs.spawnArc(from, to);
        layers.pcb.injectEnergy(from, 64, 0.85);
        randomArcAtRef.current = now + 2000 + Math.random() * 6000;
      }

      animationRef.current = window.requestAnimationFrame(tick);
    };

    animationRef.current = window.requestAnimationFrame(tick);
    return () => {
      window.removeEventListener("resize", resize);
      if (animationRef.current != null) {
        window.cancelAnimationFrame(animationRef.current);
      }
      Object.values(layers).forEach((layer) => layer.dispose());
      layersRef.current = null;
    };
  }, []);

  useEffect(() => {
    const shell = rootRef.current?.closest(".bos-auth-shell");
    if (!(shell instanceof HTMLElement)) return;

    let frameId = 0;
    const updateVars = () => {
      const gesture = gestureFrameRef.current;
      const focus = gesture.points.center ?? pointerRef.current;
      const transitionCharge = getTransitionCharge(
        telemetry,
        gesture.confidence,
        cameraState,
        immersiveState,
      );
      const miniCardScale =
        immersiveState === "immersive"
          ? 0.32 + transitionCharge * 0.03
          : immersiveState === "entering"
            ? 0.36 + transitionCharge * 0.04
            : immersiveState === "exiting"
              ? 0.4 + transitionCharge * 0.05
              : 1;
      const miniCardOpacity =
        immersiveState === "normal"
          ? 1
          : Math.min(
              0.96,
              (immersiveState === "exiting" ? 0.92 : 0.82) + transitionCharge * 0.08,
            );
      const miniCardGlow =
        cameraState === "ready"
          ? 0.42 + transitionCharge * 0.5
          : cameraState === "loading"
            ? 0.28 + transitionCharge * 0.34
            : cameraState === "error"
              ? 0.12
              : 0.2 + transitionCharge * 0.2;
      const reducedMotionMiniScale =
        immersiveState === "normal"
          ? 1
          : 0.9 + (miniCardScale - 0.9) * 0.28;
      const reducedMotionMiniOpacity =
        immersiveState === "normal"
          ? 1
          : 0.9 + (miniCardOpacity - 0.9) * 0.45;
      const reducedMotionMiniGlow = miniCardGlow * 0.42;
      const activeSceneId = activeScene?.id ?? "none";
      shell.style.setProperty("--login-field-x", `${clamp01(focus.x / window.innerWidth)}`);
      shell.style.setProperty("--login-field-y", `${clamp01(focus.y / window.innerHeight)}`);
      shell.style.setProperty("--login-grip", `${(telemetry.grip / 100).toFixed(4)}`);
      shell.style.setProperty("--login-openness", `${(telemetry.openness / 100).toFixed(4)}`);
      shell.style.setProperty("--login-presence", `${gesture.confidence.toFixed(4)}`);
      shell.style.setProperty("--login-energy", `${(telemetry.energy / 100).toFixed(4)}`);
      shell.style.setProperty("--login-entering", entering ? "1" : "0");
      shell.style.setProperty("--mini-card-accent", activeScene?.ambience ?? "#00C8D4");
      shell.style.setProperty(
        "--mini-card-scale",
        `${(reducedMotion ? reducedMotionMiniScale : miniCardScale).toFixed(4)}`,
      );
      shell.style.setProperty(
        "--mini-card-opacity",
        `${(reducedMotion ? reducedMotionMiniOpacity : miniCardOpacity).toFixed(4)}`,
      );
      shell.style.setProperty(
        "--mini-card-glow",
        `${(reducedMotion ? reducedMotionMiniGlow : miniCardGlow).toFixed(4)}`,
      );
      shell.style.setProperty("--mini-card-offset", immersiveState === "normal" ? "2.6rem" : "2rem");
      shell.dataset.loginScene = activeSceneId;
      frameId = window.requestAnimationFrame(updateVars);
    };

    frameId = window.requestAnimationFrame(updateVars);
    return () => {
      window.cancelAnimationFrame(frameId);
      shell.style.removeProperty("--login-field-x");
      shell.style.removeProperty("--login-field-y");
      shell.style.removeProperty("--login-grip");
      shell.style.removeProperty("--login-openness");
      shell.style.removeProperty("--login-presence");
      shell.style.removeProperty("--login-energy");
      shell.style.removeProperty("--login-entering");
      shell.style.removeProperty("--mini-card-accent");
      shell.style.removeProperty("--mini-card-scale");
      shell.style.removeProperty("--mini-card-opacity");
      shell.style.removeProperty("--mini-card-glow");
      shell.style.removeProperty("--mini-card-offset");
      delete shell.dataset.loginScene;
    };
  }, [cameraState, entering, immersiveState, reducedMotion, telemetry]);

  useEffect(() => {
    disposedRef.current = false;
    return () => {
      disposedRef.current = true;
      if (detectionFrameRef.current != null) {
        window.cancelAnimationFrame(detectionFrameRef.current);
      }
      landmarkerRef.current?.close();
      streamRef.current?.getTracks().forEach((track) => track.stop());
      effectTimeoutsRef.current.forEach((timeout) => window.clearTimeout(timeout));
      effectTimeoutsRef.current = [];
    };
  }, []);

  useEffect(() => {
    if (!autoStartCamera || cameraState !== "idle") return;
    const timer = window.setTimeout(() => {
      void startCamera();
    }, 360);
    return () => window.clearTimeout(timer);
  }, [autoStartCamera, cameraState]);

  const transitionProfile = getSceneTransitionProfile(
    sceneTransition,
    activeScene?.id,
    transitionDirection,
    overlay.focus,
    telemetry,
    gestureFrameRef.current.confidence,
    cameraState,
    immersiveState,
    reducedMotion,
  );

  return (
    <div
      ref={rootRef}
      className={`login-immersive ${isImmersiveVisible ? "is-immersive-visible" : ""} ${
        isImmersiveMode ? "is-immersive-active" : ""
      }`}
      data-camera-state={cameraState}
      data-immersive-state={immersiveState}
      data-scene-transition={sceneTransition ?? "idle"}
      data-active-scene={activeScene?.id ?? "none"}
      data-reduced-motion={reducedMotion ? "true" : "false"}
      style={
        {
          "--scene-accent": activeScene?.ambience ?? "#00C8D4",
          "--transition-duration": `${transitionProfile.durationMs}ms`,
          "--transition-duration-long": `${Math.round(transitionProfile.durationMs * 1.14)}ms`,
          "--transition-focus-x": `${(transitionProfile.focusX * 100).toFixed(2)}%`,
          "--transition-focus-y": `${(transitionProfile.focusY * 100).toFixed(2)}%`,
          "--transition-ring-scale": transitionProfile.ringScale.toFixed(3),
          "--transition-wash-scale": transitionProfile.washScale.toFixed(3),
          "--transition-wash-opacity": transitionProfile.washOpacity.toFixed(3),
          "--transition-edge-width": transitionProfile.edgeWidth,
          "--transition-snapshot-blur": `${transitionProfile.snapshotBlurPx}px`,
          "--transition-shard-opacity": transitionProfile.shardOpacity.toFixed(3),
          "--transition-charge": transitionProfile.charge.toFixed(3),
          "--transition-motion-scale": transitionProfile.motionScale.toFixed(3),
          "--transition-snapshot-clip-start": transitionProfile.snapshotClipStart,
          "--transition-snapshot-clip-end": transitionProfile.snapshotClipEnd,
          "--transition-aperture-opacity": transitionProfile.apertureOpacity.toFixed(3),
          "--transition-aperture-scale": transitionProfile.apertureScale.toFixed(3),
        } as CSSProperties
      }
    >
      <div
        className="login-immersive__layer login-immersive__layer--atmosphere"
        ref={(node) => {
          hostsRef.current.atmosphere = node;
        }}
      />
      <div
        className="login-immersive__layer login-immersive__layer--pcb"
        ref={(node) => {
          hostsRef.current.pcb = node;
        }}
      />
      <div className="login-immersive__layer login-immersive__layer--gaussian">
        <canvas ref={gaussianCanvasRef} className="login-immersive__gaussian-canvas" />
      </div>
      <div
        className="login-immersive__layer login-immersive__layer--reactor"
        ref={(node) => {
          hostsRef.current.reactor = node;
        }}
      />
      <div
        className="login-immersive__layer login-immersive__layer--arcs"
        ref={(node) => {
          hostsRef.current.arcs = node;
        }}
      />

      <div className="login-immersive__fx" aria-hidden="true">
        <div
          className={`login-immersive__focus ${overlay.confirmRing ? "is-confirming" : ""}`}
          style={
            {
              "--focus-x": `${overlay.focus.x * 100}%`,
              "--focus-y": `${overlay.focus.y * 100}%`,
              "--energy-ball": overlay.energyBall.toFixed(3),
            } as CSSProperties
          }
        />
        <div
          className={`login-immersive__wave ${overlay.waveDirection !== 0 ? "is-active" : ""} ${
            overlay.waveDirection > 0 ? "is-right" : "is-left"
          }`}
        />
        {overlay.peaceArc ? (
          <svg className="login-immersive__peace-arc" viewBox={`0 0 ${window.innerWidth} ${window.innerHeight}`}>
            <defs>
              <linearGradient id="peace-arc-gradient" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stopColor="rgba(0,200,212,0.14)" />
                <stop offset="50%" stopColor="rgba(26,255,228,0.96)" />
                <stop offset="100%" stopColor="rgba(128,255,245,0.26)" />
              </linearGradient>
            </defs>
            <path
              d={`M ${overlay.peaceArc.from.x} ${overlay.peaceArc.from.y} Q ${
                (overlay.peaceArc.from.x + overlay.peaceArc.to.x) / 2
              } ${Math.min(overlay.peaceArc.from.y, overlay.peaceArc.to.y) - 26} ${overlay.peaceArc.to.x} ${overlay.peaceArc.to.y}`}
              className="login-immersive__peace-arc-trail"
              style={{ opacity: 0.28 + overlay.peaceArc.intensity * 0.5 }}
            />
            <path
              d={`M ${overlay.peaceArc.from.x} ${overlay.peaceArc.from.y} Q ${
                (overlay.peaceArc.from.x + overlay.peaceArc.to.x) / 2
              } ${Math.min(overlay.peaceArc.from.y, overlay.peaceArc.to.y) - 26} ${overlay.peaceArc.to.x} ${overlay.peaceArc.to.y}`}
              className="login-immersive__peace-arc-main"
              style={{ opacity: 0.45 + overlay.peaceArc.intensity * 0.5 }}
            />
          </svg>
        ) : null}
        {overlay.circlePulse ? (
          <div
            className={`login-immersive__circle-pulse ${
              overlay.circlePulse.clockwise ? "is-clockwise" : "is-counter"
            }`}
            style={
              {
                "--circle-x": `${(overlay.circlePulse.center.x / window.innerWidth) * 100}%`,
                "--circle-y": `${(overlay.circlePulse.center.y / window.innerHeight) * 100}%`,
                "--circle-size": `${overlay.circlePulse.radius}px`,
              } as CSSProperties
            }
          />
        ) : null}
        {overlay.rotationIndicator ? (
          <div
            className={`login-immersive__rotation ${overlay.rotationIndicator.delta >= 0 ? "is-positive" : "is-negative"}`}
            style={
              {
                "--rotation-x": `${(overlay.rotationIndicator.center.x / window.innerWidth) * 100}%`,
                "--rotation-y": `${(overlay.rotationIndicator.center.y / window.innerHeight) * 100}%`,
                "--rotation-strength": overlay.rotationIndicator.intensity.toFixed(3),
              } as CSSProperties
            }
          />
        ) : null}
        {overlay.spreadLink ? (
          <svg className="login-immersive__spread-link" viewBox={`0 0 ${window.innerWidth} ${window.innerHeight}`}>
            <defs>
              <linearGradient id="spread-link-gradient" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stopColor="rgba(0,200,212,0.18)" />
                <stop offset="50%" stopColor="rgba(26,255,228,0.9)" />
                <stop offset="100%" stopColor="rgba(0,200,212,0.18)" />
              </linearGradient>
            </defs>
            <path
              d={`M ${overlay.spreadLink.left.x} ${overlay.spreadLink.left.y} Q ${
                (overlay.spreadLink.left.x + overlay.spreadLink.right.x) / 2
              } ${Math.min(overlay.spreadLink.left.y, overlay.spreadLink.right.y) - 24} ${
                overlay.spreadLink.right.x
              } ${overlay.spreadLink.right.y}`}
              className="login-immersive__spread-link-main"
              style={{ opacity: 0.2 + overlay.spreadLink.strength * 0.55 }}
            />
          </svg>
        ) : null}
        {overlay.pushBeam ? (
          <svg className="login-immersive__push-beam" viewBox={`0 0 ${window.innerWidth} ${window.innerHeight}`}>
            <path
              d={`M ${overlay.pushBeam.from.x} ${overlay.pushBeam.from.y} Q ${
                (overlay.pushBeam.from.x + overlay.pushBeam.to.x) / 2
              } ${overlay.pushBeam.from.y - 26} ${overlay.pushBeam.to.x} ${overlay.pushBeam.to.y}`}
              className="login-immersive__push-beam-main"
              style={{ opacity: 0.18 + overlay.pushBeam.strength * 0.28 }}
            />
          </svg>
        ) : null}
        {overlay.spreadLink
          ? (() => {
              const spreadLink = overlay.spreadLink;
              return overlay.spreadParticles.map((particle) => {
                const x =
                  spreadLink.left.x + (spreadLink.right.x - spreadLink.left.x) * particle.t;
                const y =
                  spreadLink.left.y +
                  (spreadLink.right.y - spreadLink.left.y) * particle.t +
                  particle.offset;
                return (
                  <div
                    key={particle.id}
                    className="login-immersive__spread-particle"
                    style={
                      {
                        left: `${(x / window.innerWidth) * 100}%`,
                        top: `${(y / window.innerHeight) * 100}%`,
                        opacity: 0.25 + spreadLink.strength * 0.45,
                      } as CSSProperties
                    }
                  />
                );
              });
            })()
          : null}
        {overlay.pushBurst.map((packet) => (
          <div
            key={packet.id}
            className="login-immersive__packet"
            style={
              {
                "--packet-from-x": `${(packet.from.x / window.innerWidth) * 100}%`,
                "--packet-from-y": `${(packet.from.y / window.innerHeight) * 100}%`,
                "--packet-to-x": `${(packet.to.x / window.innerWidth) * 100}%`,
                "--packet-to-y": `${(packet.to.y / window.innerHeight) * 100}%`,
                "--packet-delay": `${packet.delay}ms`,
                "--packet-duration": `${packet.duration}ms`,
              } as CSSProperties
            }
          >
            {packet.char}
          </div>
        ))}
        <div
          className={`login-immersive__singularity ${overlay.singularity > 0 ? "is-active" : ""}`}
          style={
            {
              "--singularity-x": `${overlay.focus.x * 100}%`,
              "--singularity-y": `${overlay.focus.y * 100}%`,
              "--singularity-strength": overlay.singularity.toFixed(3),
            } as CSSProperties
          }
        />
        <div className="login-immersive__success-wash" style={{ opacity: overlay.successWash }} />
        <div className="login-immersive__flash" style={{ opacity: overlay.flash }} />
        {overlay.comboFlash ? (
          <div className="login-immersive__combo-flash">{overlay.comboFlash.label}</div>
        ) : null}
      </div>

      <div className={`login-immersive__hud ${isImmersiveVisible ? "is-visible" : ""}`}>
        <div className="login-immersive__hud-label">
          <div className="login-immersive__hud-label-en">
            {activeScene?.labelEN ?? (splatReady ? "SCENE LINKED" : "SCENE BOOTSTRAP")}
          </div>
          <div className="login-immersive__hud-label-zh">
            {activeScene?.label ?? (splatReady ? "场景在线" : "场景生成中")}
          </div>
        </div>
        <div className={`login-immersive__hud-badge ${isActiveSceneBookmarked ? "is-bookmarked" : ""}`}>
          {locale === "zh-CN"
            ? isActiveSceneBookmarked
              ? "已收藏"
              : "未收藏"
            : isActiveSceneBookmarked
              ? "BOOKMARKED"
              : "UNMARKED"}
        </div>
        <div className={`login-immersive__hud-badge login-immersive__hud-badge--freeze ${sceneFrozen ? "is-frozen" : ""}`}>
          {locale === "zh-CN"
            ? sceneFrozen
              ? "已定格"
              : "自动漂移"
            : sceneFrozen
              ? "FROZEN"
              : "AUTO-FLOAT"}
        </div>
        <div className="login-immersive__hud-badge login-immersive__hud-badge--backend">
          {locale === "zh-CN"
            ? rendererKind === "gaussian"
              ? "真实 3DGS"
              : rendererKind === "procedural"
                ? "程序化 3DGS"
                : "后端待定"
            : rendererKind === "gaussian"
              ? "REAL 3DGS"
              : rendererKind === "procedural"
                ? "PROCEDURAL 3DGS"
                : "BACKEND PENDING"}
        </div>
        <div className="login-immersive__hud-badge login-immersive__hud-badge--quality">
          {locale === "zh-CN"
            ? `${rendererQualityTier.toUpperCase()} · ${rendererFps} FPS`
            : `${rendererQualityTier.toUpperCase()} · ${rendererFps} FPS`}
        </div>
        {canExitImmersive ? (
          <button
            type="button"
            className="login-immersive__hud-exit"
            onClick={() => {
              requestImmersiveExit();
            }}
          >
            {locale === "zh-CN" ? "退出沉浸" : "EXIT IMMERSIVE"}
          </button>
        ) : null}
        <div className="login-immersive__hud-nav">
          {locale === "zh-CN"
            ? "← 横扫切换场景 · 上扫下潜 / 下扫回退 · 推掌前进 / 拉掌后退 · 单指退出 · 键盘方向键可兜底 →"
            : "← Swipe to switch · Swipe up/down for depth · Push/pull camera · Point to exit · Arrow keys fallback →"}
        </div>
        {annotationsVisible && activeAnnotations ? (
          <div className="login-immersive__annotation-card">
            <div className="login-immersive__annotation-title">
              {locale === "zh-CN" ? "场景注释" : "SCENE ANNOTATIONS"}
            </div>
            {(locale === "zh-CN" ? activeAnnotations.zh : activeAnnotations.en).map((item) => (
              <div key={item} className="login-immersive__annotation-item">
                {item}
              </div>
            ))}
          </div>
        ) : null}
        <div className="login-immersive__hud-dots" aria-hidden="true">
          {sceneList.map((scene, index) => (
            <button
              type="button"
              key={scene.id}
              className={`login-immersive__hud-dot ${index === activeSceneIndex ? "is-active" : ""} ${
                bookmarkedScenes.includes(scene.id) ? "is-bookmarked" : ""
              }`}
              aria-label={`${scene.labelEN} ${scene.label}`}
              onClick={() =>
                jumpToSceneIndex(
                  index,
                  index > activeSceneIndex ? "page-right" : "page-left",
                )
              }
            />
          ))}
        </div>
        <div className="login-immersive__mini-hint">
          {locale === "zh-CN"
            ? "点击右下角登录浮窗返回主登录态"
            : "Click the mini login card to return"}
        </div>
      </div>

      <div
        className={`login-immersive__transition-fx ${sceneTransition ? "is-active" : ""} ${
          sceneTransition ? `is-${sceneTransition}` : ""
        }`}
        data-active-scene={activeScene?.id ?? "none"}
        style={
          {
            "--scene-accent": activeScene?.ambience ?? "#00C8D4",
          } as CSSProperties
        }
        aria-hidden="true"
      >
        {transitionSnapshot ? (
          <div
            className={`login-immersive__transition-snapshot ${
              transitionDirection > 0 ? "is-forward" : "is-backward"
            }`}
            style={{ backgroundImage: `url(${transitionSnapshot})` }}
          />
        ) : null}
        <div className="login-immersive__transition-aperture" />
        <div className="login-immersive__transition-wash" />
        <div className="login-immersive__transition-edge" />
        <div className="login-immersive__transition-ring" />
        <div className="login-immersive__transition-shards" />
      </div>

      <LoginSignalPanel
        title={copy.panelTitle}
        body={copy.panelBody}
        hint={copy.panelHint}
        telemetry={telemetry}
        panelCollapsed={signalPanelCollapsed}
        onTogglePanel={() => setSignalPanelCollapsed((value) => !value)}
        panelCollapseLabel={copy.collapseSignal}
        panelExpandLabel={copy.expandSignal}
        metricLabels={{
          signal: copy.metricSignal,
          grip: copy.metricGrip,
          openness: copy.metricOpenness,
          arcLoad: copy.metricArcLoad,
          ekg: copy.metricEkg,
        }}
        guideTitle={copy.guideTitle}
        guideItems={guideItems}
        collapsed={guideCollapsed}
        onToggleGuide={onToggleGuide}
        collapseLabel={copy.guideCollapse}
        expandLabel={copy.guideExpand}
      />

      <div
        className={`login-immersive__camera ${cameraPanelCollapsed ? "is-collapsed" : ""}`}
      >
        <div className="login-immersive__camera-header">
          <div className="login-immersive__camera-topline">
            <span className="login-immersive__camera-badge">
              <Hand className="h-3.5 w-3.5" />
              {cameraState === "ready" ? copy.handDetected : copy.fallbackMode}
            </span>
            <button
              type="button"
              className="login-immersive__panel-toggle"
              onClick={() => setCameraPanelCollapsed((value) => !value)}
              aria-label={cameraPanelCollapsed ? copy.expandCamera : copy.collapseCamera}
            >
              {cameraPanelCollapsed ? (
                <ChevronLeft className="h-4 w-4" />
              ) : (
                <ChevronRight className="h-4 w-4" />
              )}
            </button>
          </div>
          {!cameraPanelCollapsed ? (
            <>
              <span className="login-immersive__camera-permission">
                <Languages className="h-3.5 w-3.5" />
                {copy.permissionStateLabel}: {permissionLabel}
              </span>
              <span className="login-immersive__camera-note">
                {cameraState === "denied" || cameraState === "error" ? (
                  <TriangleAlert className="h-3.5 w-3.5" />
                ) : cameraState === "loading" ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Camera className="h-3.5 w-3.5" />
                )}
                {cameraNote}
              </span>
            </>
          ) : null}
        </div>

        {!cameraPanelCollapsed ? (
          <>
            <div className="login-immersive__camera-stage">
              <video ref={videoRef} className="login-immersive__video" muted playsInline />
              <canvas ref={previewCanvasRef} className="login-immersive__video-overlay" />
              <div className="login-immersive__video-scan" />
            </div>

            <div className="login-immersive__camera-actions">
              <Button
                type="button"
                size="sm"
                variant="outline"
                className="login-immersive__camera-button"
                onClick={() => {
                  onAutoStartCameraChange?.(true);
                  void startCamera();
                }}
                loading={cameraState === "loading"}
              >
                {cameraState === "idle" || cameraState === "ready"
                  ? copy.enableCamera
                  : copy.retryCamera}
              </Button>
              <p className="login-immersive__gesture-status">{gestureStatus}</p>
              <p className="login-immersive__camera-memory">
                {autoStartCamera ? copy.cameraRememberOn : copy.cameraRememberOff}
              </p>
              <p className="login-immersive__permission-hint">{copy.permissionHint}</p>
            </div>
          </>
        ) : (
          <div className="login-immersive__camera-collapsed-state">
            <div className="login-immersive__camera-collapsed-note">{copy.permissionStateLabel}</div>
            <div className="login-immersive__camera-collapsed-preview">
              <strong>{cameraState === "ready" ? copy.handDetected : copy.fallbackMode}</strong>
              <span>{cameraNote}</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
