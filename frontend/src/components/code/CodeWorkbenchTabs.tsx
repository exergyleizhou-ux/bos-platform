import { Diff, FileCode2, FolderTree, PackageCheck, ScrollText } from "lucide-react";
import { useMemo, useState } from "react";

import { CardBody, CardHeader } from "@/components/ui/Card";
import { CockpitPanel } from "@/components/ui/Cockpit";
import { SurfaceTile, SurfaceTileButton } from "@/components/ui/SurfaceTile";
import { translateText } from "@/lib/i18n";
import { TabPanel, Tabs } from "@/components/ui/Tabs";
import { formatDateTime } from "@/lib/utils";
import type {
  CodeArtifact,
  CodeDiffResponse,
  CodeVerificationResponse,
  CodeWorkspaceFileResponse,
  CodeWorkspaceTreeResponse,
} from "@/types/code";

interface CodeWorkbenchTabsProps {
  tree?: CodeWorkspaceTreeResponse;
  file?: CodeWorkspaceFileResponse;
  diff?: CodeDiffResponse;
  verification?: CodeVerificationResponse;
  artifacts?: CodeArtifact[];
  selectedFilePath?: string;
  onSelectFile?: (path: string) => void;
}

export function CodeWorkbenchTabs({
  tree,
  file,
  diff,
  verification,
  artifacts,
  selectedFilePath,
  onSelectFile,
}: CodeWorkbenchTabsProps) {
  const [activeTab, setActiveTab] = useState("tree");
  const tabs = useMemo(
    () => [
      { id: "tree", label: "File Tree", icon: <FolderTree className="h-4 w-4" /> },
      { id: "file", label: "Current File", icon: <FileCode2 className="h-4 w-4" /> },
      { id: "diff", label: "Diff Inspector", icon: <Diff className="h-4 w-4" /> },
      { id: "verification", label: "Verification", icon: <PackageCheck className="h-4 w-4" /> },
      { id: "artifacts", label: "Artifacts", icon: <ScrollText className="h-4 w-4" /> },
    ],
    [],
  );

  return (
    <CockpitPanel className="h-full min-h-[36rem] p-5 lg:p-6">
      <CardHeader
        title={translateText("Workspace Surface")}
        description={translateText("Tenant-scoped files, diffs, verification and artifacts.")}
      />
      <CardBody className="space-y-4">
        <Tabs tabs={tabs} activeTab={activeTab} onChange={setActiveTab} />

        <TabPanel tabId="tree" activeTab={activeTab}>
          <div className="max-h-[30rem] space-y-2 overflow-auto rounded-2xl border border-white/8 bg-surface-950/70 p-3">
            {tree?.items.length ? (
              tree.items.map((item) => (
                <SurfaceTileButton
                  key={item.path}
                  disabled={item.node_type !== "file"}
                  onClick={() => item.node_type === "file" && onSelectFile?.(item.path)}
                  selected={selectedFilePath === item.path}
                  className={`flex w-full items-center justify-between rounded-xl px-3 py-2 text-left text-xs ${
                    item.node_type !== "file" ? "cursor-default opacity-80" : ""
                  }`}
                >
                  <span>{item.node_type === "directory" ? `${translateText("DIR")} ${item.path}` : item.path}</span>
                  <span className="text-[10px] uppercase tracking-[0.18em] text-surface-500">
                    {item.node_type}
                  </span>
                </SurfaceTileButton>
              ))
            ) : (
              <p className="p-2 text-sm text-surface-400">{translateText("No workspace tree available.")}</p>
            )}
          </div>
        </TabPanel>

        <TabPanel tabId="file" activeTab={activeTab}>
          <pre className="max-h-[30rem] overflow-auto rounded-2xl border border-white/8 bg-surface-950/70 p-4 text-xs text-surface-300">
            {file?.content || translateText("No file selected.")}
          </pre>
        </TabPanel>

        <TabPanel tabId="diff" activeTab={activeTab}>
          <pre className="rounded-2xl border border-white/8 bg-surface-950/70 p-4 text-xs text-surface-300">
            {diff?.diff_summary || translateText("No diff artifact yet.")}
          </pre>
        </TabPanel>

        <TabPanel tabId="verification" activeTab={activeTab}>
          <div className="space-y-3">
            {verification?.stages.length ? (
              verification.stages.map((stage) => (
                <SurfaceTile key={stage.id} className="p-3">
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-sm font-medium text-white">{stage.verification_stage}</p>
                    <p className="text-xs uppercase tracking-[0.18em] text-surface-400">
                      {stage.verification_status}
                    </p>
                  </div>
                  {stage.summary ? <p className="mt-2 text-sm text-surface-300">{stage.summary}</p> : null}
                </SurfaceTile>
              ))
            ) : (
              <p className="text-sm text-surface-400">{translateText("No verification data yet.")}</p>
            )}
          </div>
        </TabPanel>

        <TabPanel tabId="artifacts" activeTab={activeTab}>
          <div className="space-y-3">
            {artifacts?.length ? (
              artifacts.map((artifact) => (
                <SurfaceTile key={artifact.id} className="p-3">
                  <p className="text-sm font-medium text-white">{artifact.artifact_type}</p>
                  <p className="mt-1 text-sm text-surface-300">{artifact.diff_summary || translateText("No summary")}</p>
                  <p className="mt-2 text-[11px] uppercase tracking-[0.18em] text-surface-500">
                    {formatDateTime(artifact.created_at)}
                  </p>
                </SurfaceTile>
              ))
            ) : (
              <p className="text-sm text-surface-400">{translateText("No artifacts yet.")}</p>
            )}
          </div>
        </TabPanel>
      </CardBody>
    </CockpitPanel>
  );
}
