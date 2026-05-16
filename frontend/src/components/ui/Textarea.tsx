import {
  useCallback,
  forwardRef,
  useEffect,
  useRef,
  useState,
  type TextareaHTMLAttributes,
} from "react";

import { translateText } from "@/lib/i18n";
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
      onCompositionStart,
      onCompositionEnd,
      value,
      defaultValue,
      ...props
    },
    ref,
  ) => {
    const textareaId = id ?? props.name ?? label?.toLowerCase().replace(/\s+/g, "-");
    const [charCount, setCharCount] = useState(() => String(value ?? defaultValue ?? "").length);
    const internalRef = useRef<HTMLTextAreaElement | null>(null);
    const resizeFrameRef = useRef<number | null>(null);
    const composingRef = useRef(false);

    const setRefs = (element: HTMLTextAreaElement | null) => {
      internalRef.current = element;
      if (typeof ref === "function") ref(element);
      else if (ref) ref.current = element;
    };

    const handleAutoResize = useCallback(() => {
      if (autoResize && internalRef.current) {
        const textarea = internalRef.current;
        textarea.style.height = "auto";
        textarea.style.height = `${textarea.scrollHeight}px`;
      }
    }, [autoResize]);

    const queueAutoResize = useCallback(() => {
      if (!autoResize || composingRef.current || typeof window === "undefined") return;
      if (resizeFrameRef.current !== null) {
        window.cancelAnimationFrame(resizeFrameRef.current);
      }
      resizeFrameRef.current = window.requestAnimationFrame(() => {
        resizeFrameRef.current = null;
        handleAutoResize();
      });
    }, [autoResize, handleAutoResize]);

    useEffect(() => {
      queueAutoResize();
      return () => {
        if (resizeFrameRef.current !== null) {
          window.cancelAnimationFrame(resizeFrameRef.current);
          resizeFrameRef.current = null;
        }
      };
    }, [queueAutoResize, value]);

    const handleChange = (event: React.ChangeEvent<HTMLTextAreaElement>) => {
      setCharCount(event.target.value.length);
      onChange?.(event);
      queueAutoResize();
    };

    return (
      <div className="w-full">
        {label ? (
          <label
            htmlFor={textareaId}
            className="mb-1.5 block text-sm font-medium text-surface-300"
          >
            {translateText(label)}
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
          onCompositionStart={(event) => {
            composingRef.current = true;
            onCompositionStart?.(event);
          }}
          onCompositionEnd={(event) => {
            composingRef.current = false;
            onCompositionEnd?.(event);
            queueAutoResize();
          }}
          className={cn(
            "block w-full rounded-[22px] border px-3.5 py-3 text-sm text-white transition-all duration-150",
            "bg-[linear-gradient(180deg,rgba(255,250,241,0.08),rgba(255,255,255,0.04))]",
            "placeholder:text-surface-500 resize-y focus:outline-none focus:ring-2 focus:ring-offset-0",
            "disabled:cursor-not-allowed disabled:opacity-50",
            autoResize && "resize-none overflow-hidden",
            error
              ? "border-red-400/24 focus:border-red-400 focus:ring-red-400/20"
              : "border-white/8 focus:border-brand-400/28 focus:ring-brand-400/14 hover:border-white/12",
            className,
          )}
          placeholder={props.placeholder ? translateText(props.placeholder) : props.placeholder}
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
                {translateText(error)}
              </p>
            ) : null}
            {!error && helperText ? (
              <p id={`${textareaId}-helper`} className="text-xs text-surface-500">
                {translateText(helperText)}
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
