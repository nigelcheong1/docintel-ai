"use client";

import { useEffect } from "react";

export function CursorSpotlight() {
  useEffect(() => {
    if (typeof window.matchMedia !== "function") {
      return;
    }

    const canHover = window.matchMedia("(hover: hover) and (pointer: fine)").matches;
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (!canHover || reduceMotion) {
      return;
    }

    function handlePointerMove(event: PointerEvent) {
      document.documentElement.style.setProperty("--cursor-x", `${event.clientX}px`);
      document.documentElement.style.setProperty("--cursor-y", `${event.clientY}px`);
    }

    window.addEventListener("pointermove", handlePointerMove, { passive: true });
    return () => window.removeEventListener("pointermove", handlePointerMove);
  }, []);

  return <div className="cursor-spotlight pointer-events-none fixed inset-0 z-0 hidden md:block" aria-hidden="true" />;
}
