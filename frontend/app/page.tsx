"use client";

import { useMemo } from "react";
import dynamic from "next/dynamic";
import { AnimatePresence } from "framer-motion";
import CommandCenter from "./components/CommandCenter";
import Inspector from "./components/Inspector";
import StatusBar from "./components/StatusBar";
import { useAppStore } from "./store/useAppStore";

// Semantic-first graph viewer (SSR disabled for WebGL).
const SemanticGraphViewer = dynamic(
  () => import("./components/SemanticGraphViewer"),
  { ssr: false }
);

export default function Home() {
  const isPDFViewerOpen = useAppStore((state) => state.isPDFViewerOpen);
  const selectedNodeContext = useAppStore((state) => state.selectedNodeContext);
  const isGraphFocused = useAppStore((state) => state.isGraphFocused);
  const shouldRenderGraph = true;
  
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
        {shouldRenderGraph ? <SemanticGraphViewer /> : null}
        {!shouldRenderGraph && (
          <div className="w-full h-full flex items-center justify-center">
            <div className="max-w-xl text-center px-6">
              <p className="text-sm text-cyan-300/90 font-mono">MindMap-AI</p>
              <p className="mt-2 text-xs text-white/80 font-mono">
                Upload a research PDF, then ask grounded questions to get answers, evidence clusters, and citation trails.
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Spatial HUD Panels (Z-10+) */}
      <div className="fixed inset-0 z-10 pointer-events-none">
        {/* Command Center (Left Panel) */}
        <div className="pointer-events-auto">
          <CommandCenter />
        </div>

        {/* Inspector (Right Panel) */}
        <AnimatePresence>
          {(isPDFViewerOpen || !!selectedNodeContext) && (
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
