/**
 * BOS Pipeline v9.0 �� Confirm Dialog
 *
 * Pre-built confirmation modal for delete/destructive actions.
 */

import { AlertTriangle, Trash2, Info } from "lucide-react";
import { Modal } from "@/components/ui/Modal";
import { Button } from "@/components/ui/Button";
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
    iconBg: "bg-red-50 text-red-600 dark:bg-red-900/20 dark:text-red-400",
    button: "danger" as const,
  },
  warning: {
    icon: <AlertTriangle className="h-6 w-6" />,
    iconBg:
      "bg-amber-50 text-amber-600 dark:bg-amber-900/20 dark:text-amber-400",
    button: "primary" as const,
  },
  info: {
    icon: <Info className="h-6 w-6" />,
    iconBg:
      "bg-blue-50 text-blue-600 dark:bg-blue-900/20 dark:text-blue-400",
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
    <Modal open={open} onClose={onClose} size="sm">
      <div className="flex flex-col items-center text-center">
        {/* Icon */}
        <div
          className={cn(
            "mb-4 flex h-14 w-14 items-center justify-center rounded-full",
            config.iconBg,
          )}
        >
          {config.icon}
        </div>

        {/* Title */}
        <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100">
          {title}
        </h3>

        {/* Message */}
        <p className="mt-2 text-sm text-surface-500 dark:text-surface-400">
          {message}
        </p>

        {/* Actions */}
        <div className="mt-6 flex w-full gap-3">
          <Button
            variant="secondary"
            fullWidth
            onClick={onClose}
            disabled={loading}
          >
            {cancelLabel}
          </Button>
          <Button
            variant={config.button}
            fullWidth
            onClick={handleConfirm}
            loading={loading}
          >
            {confirmLabel}
          </Button>
        </div>
      </div>
    </Modal>
  );
}
