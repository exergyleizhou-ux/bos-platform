/**
 * BOS Pipeline v9.0 -useDebounce Hook
 *
 * Debounces a value with a configurable delay.
 */

import { useState, useEffect } from "react";

/**
 * Returns a debounced version of the provided value.
 *
 * @param value The value to debounce
 * @param delay Debounce delay in milliseconds (default 300)
 */
export function useDebounce<T>(value: T, delay: number = 300): T {
 const [debouncedValue, setDebouncedValue] = useState<T>(value);

 useEffect(() => {
 const timer = setTimeout(() => {
 setDebouncedValue(value);
 }, delay);

 return () => {
 clearTimeout(timer);
 };
 }, [value, delay]);

 return debouncedValue;
}

/**
 * Debounced callback version (fire-and-forget).
 */
export function useDebouncedCallback<Args extends unknown[]>(
 callback: (...args: Args) => void,
 delay: number = 300,
): (...args: Args) => void {
 const [timer, setTimer] = useState<ReturnType<typeof setTimeout> | null>(
 null,
 );

 return (...args: Args) => {
 if (timer) clearTimeout(timer);
 setTimer(
 setTimeout(() => {
 callback(...args);
 }, delay),
 );
 };
}
