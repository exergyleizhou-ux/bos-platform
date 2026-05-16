import { useMutation, useQuery } from "@tanstack/react-query";
import toast from "react-hot-toast";

import { mediaApi } from "@/api/mediaApi";
import type {
  RemotionPresetCreateRequest,
  RemotionPresetUpdateRequest,
  RemotionRenderRequest,
  RemotionSuggestRequest,
} from "@/types/media";

export const remotionMediaKeys = {
  all: ["remotion-media"] as const,
  health: () => [...remotionMediaKeys.all, "health"] as const,
  templates: () => [...remotionMediaKeys.all, "templates"] as const,
  presets: () => [...remotionMediaKeys.all, "presets"] as const,
  renders: () => [...remotionMediaKeys.all, "renders"] as const,
};

export function useRemotionHealth() {
  return useQuery({
    queryKey: remotionMediaKeys.health(),
    queryFn: mediaApi.getHealth,
    staleTime: 30_000,
  });
}

export function useRemotionTemplates() {
  return useQuery({
    queryKey: remotionMediaKeys.templates(),
    queryFn: mediaApi.listTemplates,
    staleTime: 60_000,
  });
}

export function useRemotionPresets() {
  return useQuery({
    queryKey: remotionMediaKeys.presets(),
    queryFn: mediaApi.listPresets,
    staleTime: 15_000,
  });
}

export function useRemotionRenderHistory() {
  return useQuery({
    queryKey: remotionMediaKeys.renders(),
    queryFn: mediaApi.listRenders,
    staleTime: 15_000,
  });
}

export function useRemotionRender() {
  return useMutation({
    mutationFn: (payload: RemotionRenderRequest) => mediaApi.render(payload),
    onSuccess: (data) => {
      toast.success(data.kind === "still" ? "Image rendered" : "Animation rendered");
    },
    onError: () => {
      toast.error("Remotion render failed");
    },
  });
}

export function useRemotionSuggest() {
  return useMutation({
    mutationFn: (payload: RemotionSuggestRequest) => mediaApi.suggest(payload),
    onSuccess: () => {
      toast.success("Brief translated into a media suggestion");
    },
    onError: () => {
      toast.error("Could not generate a suggestion from the brief");
    },
  });
}

export function useCreateRemotionPreset() {
  return useMutation({
    mutationFn: (payload: RemotionPresetCreateRequest) => mediaApi.createPreset(payload),
    onSuccess: () => {
      toast.success("Campaign preset saved");
    },
    onError: () => {
      toast.error("Could not save campaign preset");
    },
  });
}

export function useDeleteRemotionPreset() {
  return useMutation({
    mutationFn: (presetId: string) => mediaApi.deletePreset(presetId),
    onSuccess: () => {
      toast.success("Campaign preset removed");
    },
    onError: () => {
      toast.error("Could not remove campaign preset");
    },
  });
}

export function useUpdateRemotionPreset() {
  return useMutation({
    mutationFn: ({ presetId, payload }: { presetId: string; payload: RemotionPresetUpdateRequest }) =>
      mediaApi.updatePreset(presetId, payload),
    onSuccess: () => {
      toast.success("Campaign preset updated");
    },
    onError: () => {
      toast.error("Could not update campaign preset");
    },
  });
}
