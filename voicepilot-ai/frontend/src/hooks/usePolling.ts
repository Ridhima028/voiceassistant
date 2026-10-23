import { useEffect, useRef } from "react";

/**
 * Calls `callback` every `intervalMs` while `active` is true. The latest
 * callback is always used, so callers don't need to memoise it.
 */
export function usePolling(callback: () => void, intervalMs: number, active: boolean): void {
  const saved = useRef(callback);

  useEffect(() => {
    saved.current = callback;
  }, [callback]);

  useEffect(() => {
    if (!active) return;
    const id = window.setInterval(() => saved.current(), intervalMs);
    return () => window.clearInterval(id);
  }, [intervalMs, active]);
}
