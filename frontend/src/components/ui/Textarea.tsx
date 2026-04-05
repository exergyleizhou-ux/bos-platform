import {
  forwardRef,
  useEffect,
  useRef,
  useState,
  type TextareaHTMLAttributes,
} from "react";

import { cn } from "@/lib/utils";

interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  error?: string;
  helperText?: string;
  showCount?: boolean;
  autoResize?: boolean;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  (
    {
      label,
      error,
      helperText,
      showCount,
      autoResize,
      maxLength,
      className,
      id,
      required,
      onChange,
      value,
      defaultValue,
      ...props
    },
    ref,
  ) => {
    const textareaId = id ?? props.name ?? label?.toLowerCase().replace(/\s+/g, "-");
    const [charCount, setCharCount] = useState(() => String(value ?? defaultValue ?? "").length);
    const internalRef = useRef<HTMLTextAreaElement | null>(null);

    const setRefs = (element: HTMLTextAreaElement | null) => {
      internalRef.current = element;
      if (typeof ref === "function") ref(element);
      else if (ref) ref.current = element;
    };

    const handleAutoResize = () => {
      if (autoResize && internalRef.current) {
        internalRef.current.style.height = "auto";
        internalRef.current.style.height = `${internalRef.current.scrollHeight}px`;
      }
    };

    useEffect(() => {
      handleAutoResize();
    }, [value]);

    const handleChange = (event: React.ChangeEvent<HTMLTextAreaElement>) => {
      setCharCount(event.target.value.length);
      handleAutoResize();
      onChange?.(event);
    };

    return (
      <div className="w-full">
        {label ? (
          <label
            htmlFor={textareaId}
            className="mb-1.5 block text-sm font-medium text-surface-300"
          >
            {label}
            {required ? <span className="ml-0.5 text-red-400">*</span> : null}
          </label>
        ) : null}

        <textarea
          ref={setRefs}
          id={textareaId}
          rows={props.rows ?? 3}
          maxLength={maxLength}
          value={value}
          defaultValue={defaultValue}
          onChange={handleChange}
          className={cn(
            "block w-full rounded-2xl border bg-white/6 px-3 py-2.5 text-sm text-white transition-colors",
            "placeholder:text-surface-500 resize-y focus:outline-none focus:ring-2 focus:ring-offset-0",
            "disabled:cursor-not-allowed disabled:opacity-50",
            autoResize && "resize-none overflow-hidden",
            error
              ? "border-red-400/30 focus:border-red-400 focus:ring-red-400/25"
              : "border-white/10 focus:border-brand-400/40 focus:ring-brand-400/20",
            className,
          )}
          aria-invalid={!!error}
          aria-describedby={
            error
              ? `${textareaId}-error`
              : helperText
                ? `${textareaId}-helper`
                : undefined
          }
          {...props}
        />

        <div className="mt-1 flex items-start justify-between gap-2">
          <div className="flex-1">
            {error ? (
              <p id={`${textareaId}-error`} className="text-xs text-red-300" role="alert">
                {error}
              </p>
            ) : null}
            {!error && helperText ? (
              <p id={`${textareaId}-helper`} className="text-xs text-surface-500">
                {helperText}
              </p>
            ) : null}
          </div>

          {showCount && maxLength ? (
            <p
              className={cn(
                "flex-shrink-0 text-xs",
                charCount > maxLength * 0.9 ? "text-amber-300" : "text-surface-500",
                charCount >= maxLength && "text-red-300",
              )}
            >
              {charCount}/{maxLength}
            </p>
          ) : null}
        </div>
      </div>
    );
  },
);

Textarea.displayName = "Textarea";
