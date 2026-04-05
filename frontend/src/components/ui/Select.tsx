import { forwardRef, type SelectHTMLAttributes } from "react";
import { ChevronDown } from "lucide-react";

import { cn } from "@/lib/utils";

interface SelectOption {
  value: string;
  label: string;
  disabled?: boolean;
}

interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  options: SelectOption[];
  error?: string;
  helperText?: string;
  placeholder?: string;
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(
  (
    {
      label,
      options,
      error,
      helperText,
      placeholder,
      className,
      id,
      required,
      ...props
    },
    ref,
  ) => {
    const selectId = id ?? props.name ?? label?.toLowerCase().replace(/\s+/g, "-");

    return (
      <div className="w-full">
        {label ? (
          <label
            htmlFor={selectId}
            className="mb-1.5 block text-sm font-medium text-surface-300"
          >
            {label}
            {required ? <span className="ml-0.5 text-red-400">*</span> : null}
          </label>
        ) : null}

        <div className="relative">
          <select
            ref={ref}
            id={selectId}
            className={cn(
              "block w-full appearance-none rounded-2xl border bg-white/6 px-3 py-2.5 pr-10 text-sm text-white transition-colors",
              "focus:outline-none focus:ring-2 focus:ring-offset-0",
              "disabled:cursor-not-allowed disabled:opacity-50",
              error
                ? "border-red-400/30 focus:border-red-400 focus:ring-red-400/25"
                : "border-white/10 focus:border-brand-400/40 focus:ring-brand-400/20",
              className,
            )}
            aria-invalid={!!error}
            aria-describedby={
              error
                ? `${selectId}-error`
                : helperText
                  ? `${selectId}-helper`
                  : undefined
            }
            {...props}
          >
            {placeholder ? (
              <option value="" disabled>
                {placeholder}
              </option>
            ) : null}
            {options.map((option) => (
              <option key={option.value} value={option.value} disabled={option.disabled}>
                {option.label}
              </option>
            ))}
          </select>

          <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-3 text-surface-500">
            <ChevronDown className="h-4 w-4" />
          </div>
        </div>

        {error ? (
          <p id={`${selectId}-error`} className="mt-1 text-xs text-red-300" role="alert">
            {error}
          </p>
        ) : null}

        {!error && helperText ? (
          <p id={`${selectId}-helper`} className="mt-1 text-xs text-surface-500">
            {helperText}
          </p>
        ) : null}
      </div>
    );
  },
);

Select.displayName = "Select";
