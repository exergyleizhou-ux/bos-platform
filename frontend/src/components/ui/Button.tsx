import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from "react";

import { Spinner } from "@/components/ui/Spinner";
import { translateNodeText } from "@/lib/i18n";
import { cn } from "@/lib/utils";

const VARIANTS = {
  primary:
    "border border-brand-300/18 bg-brand-500/88 text-white shadow-glow hover:bg-brand-400/92 active:bg-brand-600 focus-visible:ring-brand-300",
  secondary:
    "border border-white/8 bg-white/5 text-surface-100 hover:bg-white/8 active:bg-white/10 focus-visible:ring-surface-400",
  outline:
    "border border-white/10 bg-transparent text-surface-200 hover:bg-white/5 active:bg-white/8 focus-visible:ring-surface-400",
  ghost:
    "bg-transparent text-surface-400 hover:bg-white/5 hover:text-white active:bg-white/8 focus-visible:ring-surface-400",
  danger:
    "border border-red-400/16 bg-red-500/84 text-white hover:bg-red-500/92 active:bg-red-600 focus-visible:ring-red-300",
} as const;

const SIZES = {
  xs: "h-7 px-2 text-xs gap-1 rounded-md",
  sm: "h-9 px-3.5 text-sm gap-1.5 rounded-xl",
  md: "h-10 px-4.5 text-sm gap-2 rounded-xl",
  lg: "h-11 px-5 text-base gap-2 rounded-2xl",
  icon: "h-10 w-10 rounded-xl",
} as const;

type ButtonVariant = keyof typeof VARIANTS;
type ButtonSize = keyof typeof SIZES;

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  leftIcon?: ReactNode;
  rightIcon?: ReactNode;
  loading?: boolean;
  fullWidth?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      variant = "primary",
      size = "md",
      leftIcon,
      rightIcon,
      loading,
      fullWidth,
      disabled,
      className,
      children,
      ...props
    },
    ref,
  ) => {
    const isDisabled = disabled || loading;

    return (
      <button
        ref={ref}
        disabled={isDisabled}
        className={cn(
          "inline-flex items-center justify-center font-medium transition-all duration-150",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-0",
          "disabled:pointer-events-none disabled:opacity-50",
          VARIANTS[variant],
          SIZES[size],
          fullWidth && "w-full",
          className,
        )}
        {...props}
      >
        {loading ? (
          <Spinner size="xs" className="flex-shrink-0" />
        ) : leftIcon ? (
          <span className="flex-shrink-0">{leftIcon}</span>
        ) : null}

        {size !== "icon" && children ? (
          <span className={cn(loading && "ml-0.5")}>{translateNodeText(children)}</span>
        ) : null}

        {rightIcon && !loading ? (
          <span className="flex-shrink-0">{rightIcon}</span>
        ) : null}
      </button>
    );
  },
);

Button.displayName = "Button";
