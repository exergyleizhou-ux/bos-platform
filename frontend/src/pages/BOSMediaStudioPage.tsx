import { useEffect, useMemo, useRef, useState } from "react";
import {
  Clapperboard,
  Download,
  Image as ImageIcon,
  Wand2,
  RefreshCcw,
  Sparkles,
  Video,
} from "lucide-react";
import toast from "react-hot-toast";

import { mediaApi } from "@/api/mediaApi";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { CardBody, CardHeader } from "@/components/ui/Card";
import {
  CockpitGrid,
  CockpitMetric,
  CockpitPanel,
  CockpitSectionLabel,
} from "@/components/ui/Cockpit";
import { EmptyState, ErrorState } from "@/components/ui/EmptyState";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { SurfaceTile, SurfaceTileButton } from "@/components/ui/SurfaceTile";
import { Textarea } from "@/components/ui/Textarea";
import {
  useCreateRemotionPreset,
  useDeleteRemotionPreset,
  useRemotionHealth,
  useRemotionPresets,
  useRemotionRender,
  useRemotionRenderHistory,
  useRemotionSuggest,
  useRemotionTemplates,
  useUpdateRemotionPreset,
} from "@/hooks/useRemotionMedia";
import { downloadBlob, formatDateTime } from "@/lib/utils";
import type {
  RemotionPreset,
  RemotionPresetCreateRequest,
  RemotionPresetUpdateRequest,
  RemotionRenderKind,
  RemotionRenderResponse,
  RemotionSuggestResponse,
  RemotionTemplate,
} from "@/types/media";

type DynamicFieldState = Record<string, string>;

const DEFAULT_KIND: RemotionRenderKind = "still";

const PRESET_PACKS = [
  {
    id: "launch",
    label: "Launch",
    eyebrow: "Campaign-ready",
    brief:
      "Create a polished BOS launch visual announcing a new capability with confident product language and a premium reveal tone.",
    audience: "external",
    brandVoice: "launch",
    kind: "still" as RemotionRenderKind,
    templateId: "bos-launch-card",
  },
  {
    id: "executive",
    label: "Executive Update",
    eyebrow: "Board-facing",
    brief:
      "Create an executive-ready BOS update that compresses the signal into a calm headline, strategic subtitle, and one strong proof point.",
    audience: "executives",
    brandVoice: "executive",
    kind: "still" as RemotionRenderKind,
    templateId: "bos-metric-board",
  },
  {
    id: "ops",
    label: "Ops Signal",
    eyebrow: "Control room",
    brief:
      "Create an operations-facing BOS signal update that emphasizes current posture, execution clarity, and the next concrete move.",
    audience: "operators",
    brandVoice: "operations",
    kind: "video" as RemotionRenderKind,
    templateId: "bos-signal-beacon",
  },
  {
    id: "social",
    label: "Social Story",
    eyebrow: "Motion-first",
    brief:
      "Create a vertical BOS story with quick social pacing, a sharp headline, and a shareable motion-first frame.",
    audience: "community",
    brandVoice: "social",
    kind: "video" as RemotionRenderKind,
    templateId: "bos-story-stack",
  },
] as const;

const EXPORT_RECIPES = [
  {
    id: "web-hero",
    label: "Web Hero",
    description: "Homepage banner or product launch strip.",
    width: 1600,
    height: 900,
    kind: "still" as RemotionRenderKind,
    fps: 30,
    durationInFrames: 1,
  },
  {
    id: "wechat-poster",
    label: "WeChat Poster",
    description: "Tall poster for article embeds and community shares.",
    width: 1080,
    height: 1440,
    kind: "still" as RemotionRenderKind,
    fps: 30,
    durationInFrames: 1,
  },
  {
    id: "douyin-vertical",
    label: "Douyin Vertical",
    description: "9:16 motion canvas for short vertical video.",
    width: 1080,
    height: 1920,
    kind: "video" as RemotionRenderKind,
    fps: 30,
    durationInFrames: 180,
  },
  {
    id: "deck-header",
    label: "Deck Header",
    description: "Wide image for executive decks and board updates.",
    width: 1920,
    height: 1080,
    kind: "still" as RemotionRenderKind,
    fps: 30,
    durationInFrames: 1,
  },
] as const;

const PRESET_GROUP_OPTIONS = [
  { value: "all", label: "All groups" },
  { value: "launch", label: "Launch" },
  { value: "ops", label: "Ops" },
  { value: "board", label: "Board" },
  { value: "social", label: "Social" },
  { value: "other", label: "Other" },
] as const;

function parseTags(value: string): string[] {
  return Array.from(
    new Set(
      value
        .split(",")
        .map((item) => item.trim().toLowerCase())
        .filter(Boolean),
    ),
  ).slice(0, 8);
}

function presetGroupKey(preset: {
  tags: string[];
  brand_voice: string;
  audience: string;
  template_id: string;
}) {
  const tags = preset.tags.map((tag) => tag.toLowerCase());
  if (tags.some((tag) => ["launch", "campaign", "marketing"].includes(tag))) return "launch";
  if (tags.some((tag) => ["ops", "signal", "operations"].includes(tag))) return "ops";
  if (tags.some((tag) => ["board", "executive", "kpi", "metrics"].includes(tag))) return "board";
  if (tags.some((tag) => ["social", "story", "community"].includes(tag))) return "social";
  if (preset.brand_voice === "launch") return "launch";
  if (preset.brand_voice === "operations") return "ops";
  if (preset.brand_voice === "executive") return "board";
  if (preset.brand_voice === "social") return "social";
  if (preset.template_id === "bos-metric-board") return "board";
  if (preset.template_id === "bos-story-stack") return "social";
  if (preset.audience === "operators") return "ops";
  if (preset.audience === "executives") return "board";
  return "other";
}

function presetGroupLabel(group: string) {
  return PRESET_GROUP_OPTIONS.find((option) => option.value === group)?.label ?? group;
}

function templateSampleContent(templateId: string) {
  switch (templateId) {
    case "bos-signal-beacon":
      return {
        title: "Release posture is holding",
        subtitle:
          "Confidence is rising because the signal, contract, and portability layers are aligned again.",
        caption: "SIGNAL REVIEW",
        extraProps: {
          eyebrow: "SIGNAL REVIEW",
          status: "Ready",
          detail: "Fresh signal, contract aligned, portability checks green.",
          grid_density: 5,
        },
      };
    case "bos-story-stack":
      return {
        title: "BOS ships in motion",
        subtitle:
          "Vertical-first storytelling for launch moments, community drops, and short-form operator updates.",
        caption: "STORY STACK",
        extraProps: {
          eyebrow: "BOS STORY",
          status: "Shipping",
          callout: "Programmatic graphics and motion now render directly inside BOS.",
        },
      };
    case "bos-metric-board":
      return {
        title: "Metrics are compounding",
        subtitle:
          "Use the board layout when the story needs two proof points and one calm executive headline.",
        caption: "METRIC BOARD",
        extraProps: {
          eyebrow: "BOS METRICS",
          primary_metric_label: "Render Velocity",
          primary_metric_value: "+42%",
          secondary_metric_label: "Turnaround",
          secondary_metric_value: "Same Day",
        },
      };
    default:
      return {
        title: "Launch the next BOS story",
        subtitle:
          "A polished hero card for product reveals, internal launches, and campaign-ready announcements.",
        caption: "RENDERED WITH REMOTION",
        extraProps: {
          eyebrow: "BOS MEDIA STUDIO",
          metric_label: "Launch Window",
          metric_value: "THIS WEEK",
          orb_count: 3,
        },
      };
  }
}

function fieldPlacementCopy(templateId: string, fieldKey: string) {
  const lookup: Record<string, Record<string, string>> = {
    "bos-launch-card": {
      eyebrow: "Small label in the upper-left that sets the theme of the card.",
      metric_label: "Small label inside the right-side stat panel.",
      metric_value: "Large value inside the right-side stat panel.",
      orb_count: "Controls how many glowing background orbs appear behind the card.",
    },
    "bos-signal-beacon": {
      eyebrow: "Upper-left chip label above the main signal headline.",
      status: "Status badge inside the right-side signal panel.",
      detail: "Longer descriptive copy inside the main signal card on the right.",
      grid_density: "Changes the density of the board/grid lines in the background.",
    },
    "bos-story-stack": {
      eyebrow: "Upper-left story label at the top of the portrait canvas.",
      status: "Top-right chip showing the current story state.",
      callout: "Large callout block near the bottom of the vertical composition.",
    },
    "bos-metric-board": {
      eyebrow: "Upper-left board label for the metric layout.",
      primary_metric_label: "Label above the first large KPI card.",
      primary_metric_value: "Main value in the first large KPI card.",
      secondary_metric_label: "Label above the second KPI card.",
      secondary_metric_value: "Main value in the second KPI card.",
    },
  };

  return (
    lookup[templateId]?.[fieldKey] ??
    "Template field used by the selected composition."
  );
}

function buildInitialFieldState(template: RemotionTemplate | null): DynamicFieldState {
  if (!template) return {};
  return Object.fromEntries(
    template.fields.map((field) => [
      field.key,
      field.default == null ? "" : String(field.default),
    ]),
  );
}

function parseFieldValue(value: string, kind: RemotionTemplate["fields"][number]["kind"]) {
  if (kind === "number") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return value;
}

function templatePreviewTone(templateId: string) {
  switch (templateId) {
    case "bos-signal-beacon":
      return {
        accent: "#F8C15C",
        background: "linear-gradient(160deg, #08131D 0%, #122032 100%)",
        eyebrow: "SIGNAL",
        headline: "Release posture is moving",
        detail: "Signal-led, cinematic, wide.",
      };
    case "bos-story-stack":
      return {
        accent: "#7CFFB2",
        background: "linear-gradient(180deg, #08111C 0%, #122136 100%)",
        eyebrow: "STORY",
        headline: "BOS ships in motion",
        detail: "Portrait-first, fast, social.",
      };
    case "bos-metric-board":
      return {
        accent: "#82B8FF",
        background: "linear-gradient(155deg, #08131D 0%, #172636 100%)",
        eyebrow: "METRIC",
        headline: "Metrics are compounding",
        detail: "Board-ready, KPI-forward, wide.",
      };
    default:
      return {
        accent: "#7CFFB2",
        background: "linear-gradient(145deg, #07111F 0%, #13263A 100%)",
        eyebrow: "LAUNCH",
        headline: "Launch the next BOS story",
        detail: "Hero card, polished, campaign-ready.",
      };
  }
}

export default function BOSMediaStudioPage() {
  const health = useRemotionHealth();
  const templates = useRemotionTemplates();
  const sharedPresets = useRemotionPresets();
  const renderMutation = useRemotionRender();
  const renderHistory = useRemotionRenderHistory();
  const suggestMutation = useRemotionSuggest();
  const createPreset = useCreateRemotionPreset();
  const deletePreset = useDeleteRemotionPreset();
  const updatePreset = useUpdateRemotionPreset();

  const templateList = useMemo(() => templates.data ?? [], [templates.data]);
  const firstTemplate = templateList[0] ?? null;

  const [kind, setKind] = useState<RemotionRenderKind>(DEFAULT_KIND);
  const [exportRecipeId, setExportRecipeId] = useState("web-hero");
  const [templateId, setTemplateId] = useState("");
  const [presetName, setPresetName] = useState("");
  const [presetTagsInput, setPresetTagsInput] = useState("launch");
  const [presetSearch, setPresetSearch] = useState("");
  const [presetGroup, setPresetGroup] = useState("all");
  const [activePresetId, setActivePresetId] = useState<string | null>(null);
  const [creativeBrief, setCreativeBrief] = useState(
    "Create a polished BOS launch visual announcing that graphics and motion now render inside the workspace.",
  );
  const [audience, setAudience] = useState("general");
  const [brandVoice, setBrandVoice] = useState("balanced");
  const [title, setTitle] = useState("BOS Media Studio");
  const [subtitle, setSubtitle] = useState(
    "Programmatic graphics and motion, now rendered from inside your BOS workflow.",
  );
  const [caption, setCaption] = useState("RENDERED WITH REMOTION");
  const [accentColor, setAccentColor] = useState("#7CFFB2");
  const [backgroundColor, setBackgroundColor] = useState("#07111F");
  const [width, setWidth] = useState("1080");
  const [height, setHeight] = useState("1080");
  const [fps, setFps] = useState("30");
  const [durationInFrames, setDurationInFrames] = useState("150");
  const [dynamicFields, setDynamicFields] = useState<DynamicFieldState>({});
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [rendered, setRendered] = useState<RemotionRenderResponse | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [suggestionRationale, setSuggestionRationale] = useState<string[]>([]);
  const [suggestionSource, setSuggestionSource] = useState<"heuristic" | "model" | null>(null);
  const [presetSnapshotUrls, setPresetSnapshotUrls] = useState<Record<string, string>>({});
  const presetSnapshotUrlsRef = useRef<Record<string, string>>({});

  const selectedTemplate = useMemo(
    () => templateList.find((template) => template.id === templateId) ?? firstTemplate,
    [firstTemplate, templateId, templateList],
  );
  const filteredPresetGroups = useMemo(() => {
    const items = sharedPresets.data ?? [];
    const query = presetSearch.trim().toLowerCase();
    const filtered = items.filter((preset) => {
      const group = presetGroupKey(preset);
      if (presetGroup !== "all" && group !== presetGroup) return false;
      if (!query) return true;
      return [
        preset.name,
        preset.template_id,
        preset.creative_brief,
        preset.audience,
        preset.brand_voice,
        ...preset.tags,
      ]
        .join(" ")
        .toLowerCase()
        .includes(query);
    });

    return filtered.reduce<Record<string, RemotionPreset[]>>((accumulator, preset) => {
      const group = presetGroupKey(preset);
      accumulator[group] = accumulator[group] ? [...accumulator[group], preset] : [preset];
      return accumulator;
    }, {});
  }, [presetGroup, presetSearch, sharedPresets.data]);

  const applyTemplateDefaults = (template: RemotionTemplate) => {
    setTemplateId(template.id);
    setDynamicFields(buildInitialFieldState(template));
    setWidth(String(template.default_width));
    setHeight(String(template.default_height));
    setFps(String(template.default_fps));
    setDurationInFrames(String(template.default_duration_in_frames));
    setKind((current) => (template.supported_kinds.includes(current) ? current : template.supported_kinds[0] ?? DEFAULT_KIND));
  };

  useEffect(() => {
    if (!templateId && firstTemplate) {
      applyTemplateDefaults(firstTemplate);
    }
  }, [firstTemplate, templateId]);

  useEffect(() => {
    return () => {
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl);
      }
    };
  }, [previewUrl]);

  useEffect(() => {
    presetSnapshotUrlsRef.current = presetSnapshotUrls;
  }, [presetSnapshotUrls]);

  useEffect(() => {
    let active = true;
    const currentUrls = presetSnapshotUrls;
    const presetsWithSnapshots = (sharedPresets.data ?? []).filter((preset) => preset.snapshot_file_name);

    const loadSnapshots = async () => {
      const nextEntries: Array<[string, string]> = [];
      for (const preset of presetsWithSnapshots) {
        if (!preset.snapshot_file_name || currentUrls[preset.id]) {
          continue;
        }
        try {
          const blob = await mediaApi.fetchAssetBlob(preset.snapshot_file_name);
          nextEntries.push([preset.id, URL.createObjectURL(blob)]);
        } catch {
          // Leave the preset card without a snapshot if the asset cannot be loaded.
        }
      }

      if (!active || nextEntries.length === 0) {
        return;
      }
      setPresetSnapshotUrls((existing) => ({
        ...existing,
        ...Object.fromEntries(nextEntries),
      }));
    };

    void loadSnapshots();

    return () => {
      active = false;
    };
  }, [presetSnapshotUrls, sharedPresets.data]);

  useEffect(() => {
    const snapshotIds = new Set((sharedPresets.data ?? []).map((preset) => preset.id));
    setPresetSnapshotUrls((existing) => {
      const next = { ...existing };
      for (const [presetId, url] of Object.entries(existing)) {
        if (snapshotIds.has(presetId)) {
          continue;
        }
        URL.revokeObjectURL(url);
        delete next[presetId];
      }
      return next;
    });
  }, [sharedPresets.data]);

  useEffect(() => {
    return () => {
      Object.values(presetSnapshotUrlsRef.current).forEach((url) => URL.revokeObjectURL(url));
    };
  }, []);

  const healthReady = health.data?.ready ?? false;

  const applySuggestion = (suggestion: RemotionSuggestResponse) => {
    setTemplateId(suggestion.template_id);
    setKind(suggestion.kind);
    setTitle(suggestion.title);
    setSubtitle(suggestion.subtitle);
    setCaption(suggestion.caption);
    setAccentColor(suggestion.accent_color);
    setBackgroundColor(suggestion.background_color);
    setWidth(String(suggestion.width));
    setHeight(String(suggestion.height));
    setFps(String(suggestion.fps));
    setDurationInFrames(String(suggestion.duration_in_frames));
    setDynamicFields(
      Object.fromEntries(
        Object.entries(suggestion.extra_props ?? {}).map(([key, value]) => [key, String(value ?? "")]),
      ),
    );
    setSuggestionRationale(suggestion.rationale);
    setSuggestionSource(suggestion.source);
  };

  const handleApplyExportRecipe = (recipeId: string) => {
    const recipe = EXPORT_RECIPES.find((item) => item.id === recipeId);
    if (!recipe) return;
    setExportRecipeId(recipe.id);
    setWidth(String(recipe.width));
    setHeight(String(recipe.height));
    setFps(String(recipe.fps));
    setDurationInFrames(String(recipe.durationInFrames));
    setKind(recipe.kind);
    setSuggestionRationale((current) => [
      `Export recipe selected: ${recipe.label}`,
      ...current.filter((item) => !item.startsWith("Export recipe selected:")).slice(0, 3),
    ]);
  };

  const handleSuggest = async () => {
    const suggestion = await suggestMutation.mutateAsync({
      brief: creativeBrief,
      preferred_kind: kind,
      preferred_template_id: templateId || undefined,
      audience,
      brand_voice: brandVoice,
    });
    applySuggestion(suggestion);
  };

  const handleApplyPreset = (preset: (typeof PRESET_PACKS)[number]) => {
    setCreativeBrief(preset.brief);
    setAudience(preset.audience);
    setBrandVoice(preset.brandVoice);
    const nextTemplate = templateList.find((template) => template.id === preset.templateId);
    if (nextTemplate) {
      applyTemplateDefaults(nextTemplate);
    }
    setKind(preset.kind);
    setSuggestionSource(null);
    setSuggestionRationale([
      `Preset selected: ${preset.label}`,
      `Audience tuned for ${preset.audience}.`,
      `Voice tuned for ${preset.brandVoice}.`,
    ]);
  };

  const handleRender = async () => {
    if (!selectedTemplate) return;
    const extraProps = Object.fromEntries(
      selectedTemplate.fields.map((field) => [
        field.key,
        parseFieldValue(dynamicFields[field.key] ?? "", field.kind),
      ]),
    );
    const payload = {
      kind,
      template_id: selectedTemplate.id,
      title,
      subtitle,
      caption,
      accent_color: accentColor,
      background_color: backgroundColor,
      width: Number(width),
      height: Number(height),
      fps: Number(fps),
      duration_in_frames: Number(durationInFrames),
      extra_props: extraProps,
    };

    const response = await renderMutation.mutateAsync(payload);
    setRendered(response);
    setPreviewLoading(true);
    try {
      const blob = await mediaApi.fetchAssetBlob(response.file_name);
      setPreviewUrl((current) => {
        if (current) URL.revokeObjectURL(current);
        return URL.createObjectURL(blob);
      });
    } catch {
      toast.error("Render succeeded, but preview download failed");
    } finally {
      setPreviewLoading(false);
      void renderHistory.refetch();
    }
  };

  const handleOpenHistoryItem = async (item: RemotionRenderResponse) => {
    setRendered(item);
    setPreviewLoading(true);
    try {
      const blob = await mediaApi.fetchAssetBlob(item.file_name);
      setPreviewUrl((current) => {
        if (current) URL.revokeObjectURL(current);
        return URL.createObjectURL(blob);
      });
    } catch {
      toast.error("Could not load this render preview");
    } finally {
      setPreviewLoading(false);
    }
  };

  const handleDownload = async () => {
    if (!rendered) return;
    const blob = await mediaApi.downloadAssetBlob(rendered.file_name);
    downloadBlob(blob, rendered.file_name);
  };

  const handleLoadSample = () => {
    if (!selectedTemplate) return;
    const sample = templateSampleContent(selectedTemplate.id);
    setTitle(sample.title);
    setSubtitle(sample.subtitle);
    setCaption(sample.caption);
    setDynamicFields(
      Object.fromEntries(
        Object.entries(sample.extraProps).map(([key, value]) => [key, String(value)]),
      ),
    );
    setSuggestionRationale((current) => [
      "Loaded sample content for the selected template.",
      ...current.filter((item) => item !== "Loaded sample content for the selected template.").slice(0, 3),
    ]);
  };

  const handleSavePreset = () => {
    if (!selectedTemplate) return;
    const name = presetName.trim() || title.trim() || selectedTemplate.name;
    const payload: RemotionPresetCreateRequest = {
      name,
      tags: parseTags(presetTagsInput),
      snapshot_file_name:
        rendered?.template_id === selectedTemplate.id ? rendered.file_name : undefined,
      snapshot_kind:
        rendered?.template_id === selectedTemplate.id ? rendered.kind : undefined,
      template_id: selectedTemplate.id,
      kind,
      export_recipe_id: exportRecipeId,
      creative_brief: creativeBrief,
      audience,
      brand_voice: brandVoice,
      title,
      subtitle,
      caption,
      accent_color: accentColor,
      background_color: backgroundColor,
      width,
      height,
      fps,
      duration_in_frames: durationInFrames,
      dynamic_fields: dynamicFields,
    };
    void createPreset.mutateAsync(payload).then(() => {
      setPresetName("");
      setPresetTagsInput("");
      setActivePresetId(null);
      void sharedPresets.refetch();
    });
  };

  const handleUpdatePreset = () => {
    if (!selectedTemplate || !activePresetId) return;
    const payload: RemotionPresetUpdateRequest = {
      name: presetName.trim() || title.trim() || selectedTemplate.name,
      tags: parseTags(presetTagsInput),
      snapshot_file_name:
        rendered?.template_id === selectedTemplate.id ? rendered.file_name : undefined,
      snapshot_kind:
        rendered?.template_id === selectedTemplate.id ? rendered.kind : undefined,
      template_id: selectedTemplate.id,
      kind,
      export_recipe_id: exportRecipeId,
      creative_brief: creativeBrief,
      audience,
      brand_voice: brandVoice,
      title,
      subtitle,
      caption,
      accent_color: accentColor,
      background_color: backgroundColor,
      width,
      height,
      fps,
      duration_in_frames: durationInFrames,
      dynamic_fields: dynamicFields,
    };
    void updatePreset.mutateAsync({ presetId: activePresetId, payload }).then(() => {
      void sharedPresets.refetch();
    });
  };

  const handleApplySavedPreset = (preset: RemotionPreset) => {
    const nextTemplate = templateList.find((template) => template.id === preset.template_id);
    if (nextTemplate) {
      setTemplateId(nextTemplate.id);
    }
    setKind(preset.kind);
    setExportRecipeId(preset.export_recipe_id);
    setCreativeBrief(preset.creative_brief);
    setAudience(preset.audience);
    setBrandVoice(preset.brand_voice);
    setTitle(preset.title);
    setSubtitle(preset.subtitle);
    setCaption(preset.caption);
    setAccentColor(preset.accent_color);
    setBackgroundColor(preset.background_color);
    setWidth(preset.width);
    setHeight(preset.height);
    setFps(preset.fps);
    setDurationInFrames(preset.duration_in_frames);
    setDynamicFields(preset.dynamic_fields);
    setSuggestionSource(null);
    setSuggestionRationale([
      `Loaded saved preset: ${preset.name}`,
      `Template restored: ${preset.template_id}`,
    ]);
    setPresetTagsInput(preset.tags.join(", "));
    setPresetName(preset.name);
    setActivePresetId(preset.id);
  };

  const handleDeleteSavedPreset = (presetId: string) => {
    void deletePreset.mutateAsync(presetId).then(() => {
      if (activePresetId === presetId) {
        setActivePresetId(null);
      }
      void sharedPresets.refetch();
    });
  };

  if (health.isLoading || templates.isLoading) {
    return (
      <div className="assistant-ambient-shell space-y-6">
        <div className="assistant-ambient-backdrop" aria-hidden="true">
          <span className="assistant-ambient-orb assistant-ambient-orb-cyan" />
          <span className="assistant-ambient-orb assistant-ambient-orb-violet" />
          <span className="assistant-ambient-orb assistant-ambient-orb-white" />
          <span className="assistant-ambient-grid" />
          <span className="assistant-ambient-scan assistant-ambient-scan-a" />
          <span className="assistant-ambient-scan assistant-ambient-scan-b" />
        </div>
        <CockpitPanel className="p-5 lg:p-6">
          <CardBody className="py-12">
            <EmptyState
              icon={<RefreshCcw className="h-10 w-10 animate-spin" />}
              title="Loading media studio"
              description="Checking Remotion runtime and loading available templates."
            />
          </CardBody>
        </CockpitPanel>
      </div>
    );
  }

  if (health.isError || templates.isError) {
    return (
      <ErrorState
        title="Media studio failed to load"
        description="The Remotion runtime metadata could not be loaded."
        onRetry={() => {
          void health.refetch();
          void templates.refetch();
        }}
      />
    );
  }

  return (
    <div className="assistant-ambient-shell space-y-6">
      <div className="assistant-ambient-backdrop" aria-hidden="true">
        <span className="assistant-ambient-orb assistant-ambient-orb-cyan" />
        <span className="assistant-ambient-orb assistant-ambient-orb-violet" />
        <span className="assistant-ambient-orb assistant-ambient-orb-white" />
        <span className="assistant-ambient-grid" />
        <span className="assistant-ambient-scan assistant-ambient-scan-a" />
        <span className="assistant-ambient-scan assistant-ambient-scan-b" />
      </div>

      <CockpitPanel tone="hero" className="p-6 lg:p-7">
        <div className="flex flex-col gap-6">
          <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
            <div className="max-w-3xl">
              <CockpitSectionLabel>BOS Media Studio</CockpitSectionLabel>
              <h1 className="mt-4 text-3xl font-semibold tracking-tight text-white sm:text-[2.65rem]">
                Generate still graphics and short motion inside BOS
              </h1>
              <p className="mt-4 max-w-2xl text-sm leading-7 text-surface-300">
                Remotion is now mounted as an internal runtime. Pick a template, tune the copy and colors,
                and render either a polished PNG cover or a short MP4 animation.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <Badge variant={healthReady ? "success" : "warning"}>
                {healthReady ? "Runtime ready" : "Runtime needs setup"}
              </Badge>
              <Badge variant="info">{selectedTemplate?.name ?? "No template"}</Badge>
              <Button
                variant="secondary"
                leftIcon={<RefreshCcw className="h-4 w-4" />}
                onClick={() => {
                  void health.refetch();
                  void templates.refetch();
                }}
              >
                Refresh runtime
              </Button>
            </div>
          </div>

          <CockpitGrid className="sm:grid-cols-2 xl:grid-cols-4">
            <CockpitMetric label="Templates" value={String(templateList.length)} hint="Mounted compositions" accent="cyan" />
            <CockpitMetric label="Saved presets" value={String(sharedPresets.data?.length ?? 0)} hint="Reusable campaign packs" accent="violet" />
            <CockpitMetric label="Render history" value={String(renderHistory.data?.length ?? 0)} hint="Recent artifact runs" accent="amber" />
            <CockpitMetric label="Active kind" value={kind} hint={healthReady ? "Ready to render" : "Runtime offline"} accent="neutral" />
          </CockpitGrid>
        </div>
      </CockpitPanel>

      <div className="grid gap-6 xl:grid-cols-[1.05fr_0.95fr]">
        <CockpitPanel tone="emphasis" className="p-5 lg:p-6">
          <CardHeader
            title="Render controls"
            description="Template, copy, colors, size, and playback settings."
            action={
              <Badge variant="info">
                {selectedTemplate?.name ?? "No template"}
              </Badge>
            }
          />
          <CardBody className="space-y-5">
            <SurfaceTile className="space-y-4 rounded-[24px] p-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-white">Campaign presets</p>
                  <p className="mt-1 text-xs text-surface-400">
                    Save the current BOS media configuration and restore it later with one click.
                  </p>
                </div>
                {activePresetId ? (
                  <Badge variant="brand" size="xs">
                    Editing shared preset
                  </Badge>
                ) : null}
                {sharedPresets.data?.length ? (
                  <Button variant="ghost" size="sm" onClick={() => void sharedPresets.refetch()}>
                    Refresh
                  </Button>
                ) : null}
              </div>
              <div className="grid gap-4 sm:grid-cols-[1fr_auto]">
                <div className="grid gap-4 sm:grid-cols-2">
                  <Input
                    label="Preset name"
                    value={presetName}
                    onChange={(event) => setPresetName(event.target.value)}
                    placeholder="Weekly signal update"
                  />
                  <Input
                    label="Tags"
                    value={presetTagsInput}
                    onChange={(event) => setPresetTagsInput(event.target.value)}
                    placeholder="ops, signal, weekly"
                    helperText="Comma-separated tags for search and grouping."
                  />
                </div>
                <div className="flex items-end">
                  <div className="flex gap-2">
                    <Button
                      onClick={handleSavePreset}
                      disabled={!selectedTemplate}
                      loading={createPreset.isPending}
                    >
                      Save as new
                    </Button>
                    <Button
                      variant="secondary"
                      onClick={handleUpdatePreset}
                      disabled={!selectedTemplate || !activePresetId}
                      loading={updatePreset.isPending}
                    >
                      Update current
                    </Button>
                  </div>
                </div>
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <Input
                  label="Search presets"
                  value={presetSearch}
                  onChange={(event) => setPresetSearch(event.target.value)}
                  placeholder="Search by name, tag, brief"
                />
                <Select
                  label="Group"
                  value={presetGroup}
                  options={PRESET_GROUP_OPTIONS.map((option) => ({
                    value: option.value,
                    label: option.label,
                  }))}
                  onChange={(event) => setPresetGroup(event.target.value)}
                />
              </div>
              {sharedPresets.data?.length ? (
                Object.keys(filteredPresetGroups).length ? (
                  <div className="space-y-4">
                    {Object.entries(filteredPresetGroups).map(([group, presets]) => (
                      <div key={group} className="space-y-3">
                        <div className="flex items-center gap-2">
                          <p className="text-sm font-semibold text-white">{presetGroupLabel(group)}</p>
                          <Badge variant="neutral" size="xs">
                            {presets.length}
                          </Badge>
                        </div>
                        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                          {presets.map((preset) => (
                            <SurfaceTile
                              key={preset.id}
                              className="rounded-[22px] px-4 py-4"
                            >
                              <div className="flex items-start justify-between gap-3">
                                <div>
                                  <p className="text-sm font-semibold text-white">{preset.name}</p>
                                  <p className="mt-1 text-xs text-surface-400">{preset.template_id}</p>
                                </div>
                                <Badge variant={preset.kind === "video" ? "success" : "info"} size="xs">
                                  {preset.kind}
                                </Badge>
                              </div>
                              {preset.snapshot_file_name && presetSnapshotUrls[preset.id] ? (
                                <div className="mt-3 overflow-hidden rounded-[18px] border border-white/8 bg-black/30">
                                  {preset.snapshot_kind === "video" ? (
                                    <video
                                      src={presetSnapshotUrls[preset.id]}
                                      muted
                                      loop
                                      autoPlay
                                      className="block h-28 w-full object-cover"
                                    />
                                  ) : (
                                    <img
                                      src={presetSnapshotUrls[preset.id]}
                                      alt={`${preset.name} snapshot`}
                                      className="block h-28 w-full object-cover"
                                    />
                                  )}
                                </div>
                              ) : null}
                              <p className="mt-3 text-xs leading-6 text-surface-400">
                                {formatDateTime(preset.created_at)}
                              </p>
                              <div className="mt-3 flex flex-wrap gap-2">
                                {preset.tags.map((tag) => (
                                  <Badge key={`${preset.id}-${tag}`} variant="neutral" size="xs">
                                    {tag}
                                  </Badge>
                                ))}
                              </div>
                              <div className="mt-4 flex gap-2">
                                <Button
                                  variant="secondary"
                                  size="sm"
                                  onClick={() => handleApplySavedPreset(preset)}
                                >
                                  Edit
                                </Button>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  loading={deletePreset.isPending}
                                  onClick={() => handleDeleteSavedPreset(preset.id)}
                                >
                                  Remove
                                </Button>
                              </div>
                            </SurfaceTile>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <EmptyState
                    icon={<Sparkles className="h-10 w-10" />}
                    title="No presets match"
                    description="Try a different tag, group, or search term."
                  />
                )
              ) : (
                <EmptyState
                  icon={<Sparkles className="h-10 w-10" />}
                  title="No saved presets yet"
                  description="Save your best BOS media combinations so the team can reuse them quickly."
                />
              )}
            </SurfaceTile>

            <SurfaceTile className="space-y-4 rounded-[24px] p-4">
              <div>
                <p className="text-sm font-semibold text-white">Preset packs</p>
                <p className="mt-1 text-xs text-surface-400">
                  Start from a BOS business scenario, then refine the brief and render controls.
                </p>
              </div>
              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                {PRESET_PACKS.map((preset) => (
                  <SurfaceTileButton
                    key={preset.id}
                    onClick={() => handleApplyPreset(preset)}
                    className="rounded-[22px] px-4 py-4"
                  >
                    <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-surface-500">
                      {preset.eyebrow}
                    </p>
                    <p className="mt-2 text-sm font-semibold text-white">{preset.label}</p>
                    <p className="mt-2 text-xs leading-6 text-surface-400">{preset.brief}</p>
                    <div className="mt-3 flex flex-wrap gap-2">
                      <Badge variant="neutral" size="xs">
                        {preset.audience}
                      </Badge>
                      <Badge variant="info" size="xs">
                        {preset.brandVoice}
                      </Badge>
                    </div>
                  </SurfaceTileButton>
                ))}
              </div>
            </SurfaceTile>

            <SurfaceTile className="space-y-4 rounded-[24px] p-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-white">Creative brief</p>
                  <p className="mt-1 text-xs text-surface-400">
                    Describe the asset in one or two sentences and let BOS prefill the render controls.
                  </p>
                </div>
                {suggestionSource ? (
                  <Badge variant={suggestionSource === "model" ? "success" : "neutral"}>
                    {suggestionSource === "model" ? "AI suggestion" : "Heuristic fallback"}
                  </Badge>
                ) : null}
                <Button
                  variant="secondary"
                  size="sm"
                  leftIcon={<Wand2 className="h-4 w-4" />}
                  onClick={() => void handleSuggest()}
                  loading={suggestMutation.isPending}
                  disabled={!creativeBrief.trim()}
                >
                  Suggest
                </Button>
              </div>
              <Textarea
                label="Brief"
                rows={4}
                value={creativeBrief}
                onChange={(event) => setCreativeBrief(event.target.value)}
              />
              <div className="grid gap-4 sm:grid-cols-2">
                <Select
                  label="Audience"
                  value={audience}
                  options={[
                    { value: "general", label: "General" },
                    { value: "operators", label: "Operators" },
                    { value: "executives", label: "Executives" },
                    { value: "external", label: "External" },
                    { value: "community", label: "Community" },
                  ]}
                  onChange={(event) => setAudience(event.target.value)}
                />
                <Select
                  label="Brand voice"
                  value={brandVoice}
                  options={[
                    { value: "balanced", label: "Balanced" },
                    { value: "operations", label: "Operations" },
                    { value: "executive", label: "Executive" },
                    { value: "launch", label: "Launch" },
                    { value: "social", label: "Social" },
                  ]}
                  onChange={(event) => setBrandVoice(event.target.value)}
                />
              </div>
              <div>
                <p className="mb-2 text-sm font-medium text-surface-300">Export recipes</p>
                <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                  {EXPORT_RECIPES.map((recipe) => (
                    <SurfaceTileButton
                      key={recipe.id}
                      onClick={() => handleApplyExportRecipe(recipe.id)}
                      selected={exportRecipeId === recipe.id}
                      className="rounded-[22px] px-4 py-4"
                    >
                      <p className="text-sm font-semibold text-white">{recipe.label}</p>
                      <p className="mt-2 text-xs leading-6 text-surface-400">{recipe.description}</p>
                      <div className="mt-3 flex flex-wrap gap-2">
                        <Badge variant="neutral" size="xs">
                          {recipe.width} x {recipe.height}
                        </Badge>
                        <Badge variant={recipe.kind === "video" ? "success" : "info"} size="xs">
                          {recipe.kind}
                        </Badge>
                      </div>
                    </SurfaceTileButton>
                  ))}
                </div>
              </div>
              {suggestionRationale.length ? (
                <div className="flex flex-wrap gap-2">
                  {suggestionRationale.map((item) => (
                    <Badge key={item} variant="neutral">
                      {item}
                    </Badge>
                  ))}
                </div>
              ) : null}
            </SurfaceTile>

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="sm:col-span-2">
                <p className="mb-2 text-sm font-medium text-surface-300">Template gallery</p>
                <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                  {templateList.map((template) => (
                    <TemplatePreviewCard
                      key={template.id}
                      template={template}
                      selected={selectedTemplate?.id === template.id}
                      onSelect={() => applyTemplateDefaults(template)}
                    />
                  ))}
                </div>
              </div>
              <Select
                label="Template"
                value={templateId}
                options={templateList.map((template) => ({
                  value: template.id,
                  label: template.name,
                }))}
                onChange={(event) => {
                  const nextTemplate = templateList.find((template) => template.id === event.target.value);
                  if (nextTemplate) {
                    applyTemplateDefaults(nextTemplate);
                  }
                }}
              />
              <Select
                label="Output kind"
                value={kind}
                options={(selectedTemplate?.supported_kinds ?? [DEFAULT_KIND]).map((item) => ({
                  value: item,
                  label: item === "still" ? "Still graphic" : "Animation",
                }))}
                onChange={(event) => setKind(event.target.value as RemotionRenderKind)}
              />
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <Input label="Title" value={title} onChange={(event) => setTitle(event.target.value)} />
              <Input label="Caption" value={caption} onChange={(event) => setCaption(event.target.value)} />
            </div>
            <Textarea
              label="Subtitle"
              value={subtitle}
              onChange={(event) => setSubtitle(event.target.value)}
              rows={3}
            />

            <div className="grid gap-4 sm:grid-cols-2">
              <Input
                label="Accent color"
                value={accentColor}
                onChange={(event) => setAccentColor(event.target.value)}
              />
              <Input
                label="Background color"
                value={backgroundColor}
                onChange={(event) => setBackgroundColor(event.target.value)}
              />
            </div>

            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <Input label="Width" type="number" value={width} onChange={(event) => setWidth(event.target.value)} />
              <Input label="Height" type="number" value={height} onChange={(event) => setHeight(event.target.value)} />
              <Input label="FPS" type="number" value={fps} onChange={(event) => setFps(event.target.value)} />
              <Input
                label="Frames"
                type="number"
                value={durationInFrames}
                onChange={(event) => setDurationInFrames(event.target.value)}
                disabled={kind === "still"}
              />
            </div>

            {selectedTemplate ? (
              <SurfaceTile className="space-y-4 rounded-[24px] p-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-white">Template fields</p>
                    <p className="mt-1 text-xs text-surface-400">{selectedTemplate.description}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      leftIcon={<Sparkles className="h-4 w-4" />}
                      onClick={handleLoadSample}
                    >
                      Load sample
                    </Button>
                  </div>
                </div>
                <div className="grid gap-4 sm:grid-cols-2">
                  {selectedTemplate.fields.map((field) => {
                    const value = dynamicFields[field.key] ?? "";
                    const helper = field.helper_text ?? fieldPlacementCopy(selectedTemplate.id, field.key);
                    if (field.kind === "textarea") {
                      return (
                        <Textarea
                          key={field.key}
                          label={field.label}
                          value={value}
                          helperText={helper}
                          rows={3}
                          onChange={(event) =>
                            setDynamicFields((current) => ({ ...current, [field.key]: event.target.value }))
                          }
                        />
                      );
                    }
                    if (field.kind === "select") {
                      return (
                        <Select
                          key={field.key}
                          label={field.label}
                          value={value}
                          helperText={helper}
                          options={(field.options ?? []).map((option) => ({
                            value: option.value,
                            label: option.label,
                          }))}
                          onChange={(event) =>
                            setDynamicFields((current) => ({ ...current, [field.key]: event.target.value }))
                          }
                        />
                      );
                    }
                    return (
                      <Input
                        key={field.key}
                        label={field.label}
                        type={field.kind === "number" ? "number" : "text"}
                        value={value}
                        helperText={helper}
                        min={field.min ?? undefined}
                        max={field.max ?? undefined}
                        step={field.step ?? undefined}
                        onChange={(event) =>
                          setDynamicFields((current) => ({ ...current, [field.key]: event.target.value }))
                        }
                      />
                    );
                  })}
                </div>
              </SurfaceTile>
            ) : null}

            <div className="flex flex-wrap items-center justify-between gap-3 border-t border-white/8 pt-4">
              <div className="text-xs leading-6 text-surface-400">
                {health.data?.details?.map((line) => (
                  <div key={line}>{line}</div>
                ))}
              </div>
              <Button
                leftIcon={kind === "still" ? <ImageIcon className="h-4 w-4" /> : <Clapperboard className="h-4 w-4" />}
                onClick={() => void handleRender()}
                loading={renderMutation.isPending || previewLoading}
                disabled={!healthReady || !selectedTemplate || !title.trim()}
              >
                {kind === "still" ? "Render still" : "Render animation"}
              </Button>
            </div>
          </CardBody>
        </CockpitPanel>

        <div className="space-y-6">
          <CockpitPanel className="p-5 lg:p-6">
            <CardHeader
              title="Preview"
              description="Authenticated preview of the latest rendered artifact."
              action={
                rendered ? (
                  <Button
                    variant="secondary"
                    size="sm"
                    leftIcon={<Download className="h-4 w-4" />}
                    onClick={() => void handleDownload()}
                  >
                    Download
                  </Button>
                ) : null
              }
            />
            <CardBody>
              {previewUrl && rendered ? (
                <div className="space-y-4">
                  <div className="overflow-hidden rounded-[24px] border border-white/8 bg-black/40">
                    {rendered.kind === "still" ? (
                      <img
                        src={previewUrl}
                        alt="Rendered media preview"
                        className="block h-auto w-full"
                      />
                    ) : (
                      <video
                        src={previewUrl}
                        controls
                        autoPlay
                        loop
                        muted
                        className="block h-auto w-full"
                      />
                    )}
                  </div>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <Metric label="Template" value={rendered.template_id} />
                    <Metric label="Kind" value={rendered.kind} />
                    <Metric label="Size" value={`${rendered.width} x ${rendered.height}`} />
                    <Metric
                      label="Rendered at"
                      value={formatDateTime(rendered.created_at)}
                    />
                  </div>
                  {suggestionRationale.length ? (
                    <div className="flex flex-wrap gap-2">
                      {suggestionRationale.map((item) => (
                        <Badge key={`preview-${item}`} variant="neutral">
                          {item}
                        </Badge>
                      ))}
                    </div>
                  ) : null}
                </div>
              ) : (
                <EmptyState
                  icon={kind === "still" ? <ImageIcon className="h-12 w-12" /> : <Video className="h-12 w-12" />}
                  title="No render yet"
                  description="Generate a still or animation and the authenticated preview will appear here."
                />
              )}
            </CardBody>
          </CockpitPanel>

          <CockpitPanel className="p-5 lg:p-6">
            <CardHeader
              title="Runtime posture"
              description="Quick read on whether Remotion can render inside this BOS environment."
            />
            <CardBody className="space-y-3">
              <SurfaceTile className="rounded-[22px] px-4 py-4">
                <p className="assistant-section-kicker">Status</p>
                <p className="mt-3 text-xl font-semibold text-white">
                  {healthReady ? "Ready to render" : "Setup required"}
                </p>
                <p className="mt-2 text-sm leading-7 text-surface-300">
                  Node executable: {health.data?.node_executable ?? "Unknown"}
                </p>
              </SurfaceTile>
              <SurfaceTile className="rounded-[22px] px-4 py-4">
                <p className="assistant-section-kicker">Runtime directory</p>
                <p className="mt-3 break-all text-sm leading-7 text-surface-300">
                  {health.data?.runtime_dir}
                </p>
              </SurfaceTile>
              <SurfaceTile className="rounded-[22px] px-4 py-4">
                <p className="assistant-section-kicker">Output directory</p>
                <p className="mt-3 break-all text-sm leading-7 text-surface-300">
                  {health.data?.output_dir}
                </p>
              </SurfaceTile>
            </CardBody>
          </CockpitPanel>

          <CockpitPanel className="p-5 lg:p-6">
            <CardHeader
              title="Recent renders"
              description="Reopen a recent BOS media artifact without rendering again."
              action={
                <Button
                  variant="ghost"
                  size="sm"
                  leftIcon={<RefreshCcw className="h-4 w-4" />}
                  onClick={() => void renderHistory.refetch()}
                >
                  Refresh
                </Button>
              }
            />
            <CardBody className="space-y-3">
              {renderHistory.data?.length ? (
                renderHistory.data.map((item) => (
                  <button
                    key={item.file_name}
                    type="button"
                    onClick={() => void handleOpenHistoryItem(item)}
                    className="assistant-context-link assistant-side-panel-chip w-full rounded-[22px] px-4 py-4 text-left transition-colors hover:border-white/16 hover:bg-white/7"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-sm font-semibold text-white">{item.template_id}</p>
                        <p className="mt-1 text-xs text-surface-400">
                          {item.kind} / {item.width > 0 && item.height > 0 ? `${item.width} x ${item.height}` : "size pending"}
                        </p>
                        <p className="mt-2 text-xs leading-6 text-surface-500">
                          {formatDateTime(item.created_at)}
                        </p>
                      </div>
                      <Badge variant={item.kind === "still" ? "info" : "success"}>
                        {item.kind}
                      </Badge>
                    </div>
                  </button>
                ))
              ) : (
                <EmptyState
                  icon={<Clapperboard className="h-10 w-10" />}
                  title="No history yet"
                  description="The latest rendered PNG and MP4 assets will appear here."
                />
              )}
            </CardBody>
          </CockpitPanel>
        </div>
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <SurfaceTile className="rounded-[22px] px-4 py-3">
      <p className="assistant-section-kicker">{label}</p>
      <p className="mt-2 text-sm font-medium text-white">{value}</p>
    </SurfaceTile>
  );
}

function TemplatePreviewCard({
  template,
  selected,
  onSelect,
}: {
  template: RemotionTemplate;
  selected: boolean;
  onSelect: () => void;
}) {
  const tone = templatePreviewTone(template.id);

  return (
    <SurfaceTileButton
      onClick={onSelect}
      selected={selected}
      className="overflow-hidden rounded-[24px] p-0"
    >
      <div
        className="relative h-36 overflow-hidden border-b border-white/8"
        style={{ background: tone.background }}
      >
        <div
          className="absolute right-3 top-3 h-16 w-16 rounded-full blur-2xl"
          style={{ backgroundColor: `${tone.accent}66` }}
        />
        <div className="absolute left-4 top-4 text-[10px] font-semibold tracking-[0.24em] text-white/72">
          {tone.eyebrow}
        </div>
        <div className="absolute left-4 right-4 top-12 text-lg font-semibold leading-6 text-white">
          {tone.headline}
        </div>
        <div className="absolute left-4 right-4 bottom-4 text-xs leading-5 text-white/72">
          {tone.detail}
        </div>
      </div>
      <div className="space-y-2 px-4 py-4">
        <div className="flex items-center justify-between gap-2">
          <p className="text-sm font-semibold text-white">{template.name}</p>
          <Badge variant={selected ? "brand" : "neutral"} size="xs">
            {selected ? "Selected" : "Template"}
          </Badge>
        </div>
        <p className="text-xs leading-6 text-surface-400">{template.description}</p>
        <div className="flex flex-wrap gap-2">
          {template.supported_kinds.map((kind) => (
            <Badge key={`${template.id}-${kind}`} variant={kind === "video" ? "success" : "info"} size="xs">
              {kind}
            </Badge>
          ))}
        </div>
      </div>
    </SurfaceTileButton>
  );
}
