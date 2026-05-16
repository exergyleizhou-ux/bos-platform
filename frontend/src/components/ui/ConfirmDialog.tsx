/**
 * BOS Pipeline v9.0 -Confirm Dialog
 *
 * Pre-built confirmation modal for delete/destructive actions.
 */

import { AlertTriangle, Trash2, Info } from "lucide-react";
import { Modal } from "@/components/ui/Modal";
import { Button } from "@/components/ui/Button";
import { translateText } from "@/lib/i18n";
import { cn } from "@/lib/utils";

interface ConfirmDialogProps {
 open: boolean;
 onClose: () => void;
 onConfirm: () => void | Promise<void>;
 title?: string;
 message: string;
 confirmLabel?: string;
 cancelLabel?: string;
 variant?: "danger" | "warning" | "info";
 loading?: boolean;
}

const VARIANT_CONFIG = {
 danger: {
 icon: <Trash2 className="h-6 w-6" />,
 iconBg: "border border-red-400/18 bg-red-500/12 text-red-200",
 button: "danger" as const,
 },
 warning: {
 icon: <AlertTriangle className="h-6 w-6" />,
 iconBg: "border border-amber-400/18 bg-amber-500/12 text-amber-200",
 button: "primary" as const,
 },
 info: {
 icon: <Info className="h-6 w-6" />,
 iconBg: "border border-sky-400/18 bg-sky-500/12 text-sky-200",
 button: "primary" as const,
 },
};

export function ConfirmDialog({
 open,
 onClose,
 onConfirm,
 title = "Confirm Action",
 message,
 confirmLabel = "Confirm",
 cancelLabel = "Cancel",
 variant = "danger",
 loading,
}: ConfirmDialogProps) {
 const config = VARIANT_CONFIG[variant];

 const handleConfirm = async () => {
 await onConfirm();
 onClose();
 };

 return (
 <Modal open={open} onClose={onClose} size="sm" title={title}>
 <div className="flex flex-col items-center text-center">
 <div
 className={cn(
 "mb-2 flex h-14 w-14 items-center justify-center rounded-2xl",
 config.iconBg,
 )}
 >
 {config.icon}
 </div>
 <div className="mt-4 w-full rounded-2xl border border-white/8 bg-white/4 px-4 py-4 text-left text-sm leading-6 text-surface-300">
 {translateText(message)}
 </div>
 <div className="mt-6 flex w-full gap-3">
 <Button
 variant="secondary"
 fullWidth
 onClick={onClose}
 disabled={loading}
 >
 {translateText(cancelLabel)}
 </Button>
 <Button
 variant={config.button}
 fullWidth
 onClick={handleConfirm}
 loading={loading}
 >
 {translateText(confirmLabel)}
 </Button>
 </div>
 </div>
 </Modal>
 );
}
