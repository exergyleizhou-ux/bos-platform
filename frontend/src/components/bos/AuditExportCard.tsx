import { Download } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { CardBody, CardHeader } from "@/components/ui/Card";
import { CockpitPanel } from "@/components/ui/Cockpit";
import { SurfaceTile } from "@/components/ui/SurfaceTile";
import { translateText } from "@/lib/i18n";
import { formatDateTime } from "@/lib/utils";

interface AuditExportCardProps {
  hasAuditPacket: boolean;
  generatedAt: string | null;
  onExport: (format: "md" | "json") => void;
  exportingFormat?: "md" | "json" | null;
}

export function AuditExportCard({
  hasAuditPacket,
  generatedAt,
  onExport,
  exportingFormat = null,
}: AuditExportCardProps) {
  return (
    <CockpitPanel className="p-5 lg:p-6">
      <CardHeader
        title="Audit Export"
        description="Export both the operator-facing audit packet and the structured data package for the current batch."
      />
      <CardBody className="space-y-4">
        <SurfaceTile className="assistant-thread-shell rounded-3xl text-sm leading-6 text-surface-300">
          {hasAuditPacket
            ? `${translateText("The current audit packet is ready to export. Latest generation:")} ${formatDateTime(generatedAt)}.`
            : translateText("No audit packet is available yet. Run portability checks or a release evaluation first.")}
        </SurfaceTile>

        <div className="grid gap-3 sm:grid-cols-2">
          <Button
            variant="secondary"
            fullWidth
            leftIcon={<Download className="h-4 w-4" />}
            onClick={() => onExport("md")}
            loading={exportingFormat === "md"}
            disabled={!hasAuditPacket}
          >
            Export audit packet
          </Button>
          <Button
            variant="outline"
            fullWidth
            leftIcon={<Download className="h-4 w-4" />}
            onClick={() => onExport("json")}
            loading={exportingFormat === "json"}
            disabled={!hasAuditPacket}
          >
            Export structured data
          </Button>
        </div>
      </CardBody>
    </CockpitPanel>
  );
}
