import { forwardRef, type InputHTMLAttributes, type ReactNode } from "react";

import { translateText } from "@/lib/i18n";
import { cn } from "@/lib/utils";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  helperText?: string;
  leftIcon?: ReactNode;
  rightIcon?: ReactNode;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  (
    {
      label,
      error,
      helperText,
      leftIcon,
      rightIcon,
      className,
      id,
      required,
      ...props
    },
    ref,
  ) => {
    const inputId = id ?? props.name ?? label?.toLowerCase().replace(/\s+/g, "-");

    return (
      <div className="w-full">
        {label ? (
          <label
            htmlFor={inputId}
            className="mb-1.5 block text-sm font-medium text-surface-300"
          >
            {translateText(label)}
            {required ? <span className="ml-0.5 text-red-400">*</span> : null}
          </label>
        ) : null}

        <div className="relative">
          {leftIcon ? (
            <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-surface-500">
              {leftIcon}
            </div>
          ) : null}

          <input
            ref={ref}
            id={inputId}
            className={cn(
              "block w-full rounded-[20px] border px-3.5 py-3 text-sm text-white transition-all duration-150",
              "bg-[linear-gradient(180deg,rgba(255,250,241,0.08),rgba(255,255,255,0.04))]",
              "placeholder:text-surface-500 focus:outline-none focus:ring-2 focus:ring-offset-0",
              "disabled:cursor-not-allowed disabled:opacity-50",
              error
                ? "border-red-400/24 focus:border-red-400 focus:ring-red-400/20"
                : "border-white/8 focus:border-brand-400/28 focus:ring-brand-400/14 hover:border-white/12",
              leftIcon && "pl-10",
              rightIcon && "pr-10",
              className,
            )}
            aria-invalid={!!error}
            aria-describedby={
              error
                ? `${inputId}-error`
                : helperText
                  ? `${inputId}-helper`
                  : undefined
            }
            {...props}
            placeholder={props.placeholder ? translateText(props.placeholder) : props.placeholder}
          />

          {rightIcon ? (
            <div className="absolute inset-y-0 right-0 flex items-center pr-3">
              {rightIcon}
            </div>
          ) : null}
        </div>

        {error ? (
          <p id={`${inputId}-error`} className="mt-1 text-xs text-red-300" role="alert">
            {translateText(error)}
          </p>
        ) : null}

        {!error && helperText ? (
          <p id={`${inputId}-helper`} className="mt-1 text-xs text-surface-500">
            {translateText(helperText)}
          </p>
        ) : null}
      </div>
    );
  },
);

Input.displayName = "Input";
