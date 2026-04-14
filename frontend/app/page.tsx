"use client";

import { useMemo } from "react";
import dynamic from "next/dynamic";
import { AnimatePresence } from "framer-motion";
import CommandCenter from "./components/CommandCenter";
import Inspector from "./components/Inspector";
import StatusBar from "./components/StatusBar";
import { useAppStore } from "./store/useAppStore";

// Strict Client Separation: Import GraphViewer3D with SSR disabled
const GraphViewer3D = dynamic(
  () => import("./components/GraphViewer3D"),
  { ssr: false }
);

export default function Home() {
  const isPDFViewerOpen = useAppStore((state) => state.isPDFViewerOpen);
  const isGraphFocused = useAppStore((state) => state.isGraphFocused);
  
  // Memoize blur classes to prevent re-renders
  const graphBlurClass = useMemo(() => {
    return isPDFViewerOpen && !isGraphFocused
      ? "blur-sm brightness-50"
      : "blur-0 brightness-100";
  }, [isPDFViewerOpen, isGraphFocused]);

  return (
    <div className="relative w-screen h-screen overflow-hidden">
      {/* 3D Graph Background (Z-0) - Fixed container with proper dimensions */}
      <div
        className={`fixed inset-0 z-0 w-screen h-screen transition-all duration-500 ${graphBlurClass}`}
      >
        <GraphViewer3D />
      </div>

      {/* Spatial HUD Panels (Z-10+) */}
      <div className="fixed inset-0 z-10 pointer-events-none">
        {/* Command Center (Left Panel) */}
        <div className="pointer-events-auto">
          <CommandCenter />
        </div>

        {/* Inspector (Right Panel) */}
        <AnimatePresence>
          {isPDFViewerOpen && (
            <div className="pointer-events-auto">
              <Inspector />
            </div>
          )}
        </AnimatePresence>

        {/* Status Bar (Bottom Center) */}
        <div className="pointer-events-none">
          <StatusBar />
        </div>
      </div>
    </div>
  );
}
