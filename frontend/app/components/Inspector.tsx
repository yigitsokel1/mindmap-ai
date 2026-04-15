"use client";

import { motion, AnimatePresence } from "framer-motion";
import { X, FileText } from "lucide-react";
import { useAppStore } from "../store/useAppStore";

export default function Inspector() {
  const {
    isPDFViewerOpen,
    pdfUrl,
    pdfDocName,
    pdfPage,
    closePDFViewer,
    selectedNodeContext,
    setSelectedNodeContext,
  } = useAppStore();

  const pdfUrlWithPage: string | undefined = pdfUrl
    ? (pdfPage ? `${pdfUrl}#page=${pdfPage}` : pdfUrl)
    : undefined;

  return (
    <AnimatePresence>
      {(isPDFViewerOpen || !!selectedNodeContext) && (
        <motion.div
          initial={{ x: "100%" }}
          animate={{ x: 0 }}
          exit={{ x: "100%" }}
          transition={{ type: "spring", damping: 30, stiffness: 300 }}
          className="fixed right-4 top-4 bottom-4 w-[600px] max-w-[calc(100vw-2rem)] z-20 bg-black/40 backdrop-blur-2xl border border-white/10 rounded-2xl shadow-[0_8px_32px_rgba(0,0,0,0.6)] flex flex-col"
        >
          {/* Header */}
          <div className="flex items-center justify-between p-4 border-b border-white/10">
            <div className="flex items-center gap-2 min-w-0 flex-1">
              <FileText className="w-4 h-4 text-cyan-400 flex-shrink-0" />
              <div className="min-w-0 flex-1">
                <p className="text-xs font-mono font-semibold text-white/90 truncate">
                  {pdfDocName || "DOCUMENT"}
                </p>
                {pdfPage && (
                  <p className="text-[10px] text-white/50 font-mono mt-0.5">
                    PAGE {pdfPage}
                  </p>
                )}
              </div>
            </div>
            <button
              onClick={() => {
                closePDFViewer();
                setSelectedNodeContext(null);
              }}
              className="p-1.5 rounded-lg hover:bg-white/5 text-white/50 hover:text-white/90 transition-colors border border-transparent hover:border-white/10"
              title="Close"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {selectedNodeContext && (
            <div className="px-4 py-3 border-b border-white/10 bg-black/30">
              <p className="text-[10px] text-cyan-300 uppercase font-mono tracking-wide">
                {selectedNodeContext.label}
              </p>
              <p className="text-xs text-white/90 font-mono mt-1">{selectedNodeContext.title}</p>
              {selectedNodeContext.documentName && (
                <p className="text-[10px] text-white/60 font-mono mt-1">
                  {selectedNodeContext.documentName}
                  {selectedNodeContext.page ? ` · page ${selectedNodeContext.page}` : ""}
                </p>
              )}
            </div>
          )}

          {/* PDF Content */}
          <div className="flex-1 overflow-hidden bg-black/20 rounded-b-2xl">
            {pdfUrl ? (
              <iframe
                src={pdfUrlWithPage}
                className="w-full h-full border-0 rounded-b-2xl"
                title={pdfDocName || "PDF Viewer"}
              />
            ) : selectedNodeContext ? (
              <div className="h-full overflow-y-auto p-4">
                <p className="text-[10px] text-white/50 font-mono mb-2 uppercase tracking-wide">
                  Node Details
                </p>
                {selectedNodeContext.rawText && (
                  <p className="text-xs text-white/80 font-mono leading-relaxed mb-3">
                    {selectedNodeContext.rawText}
                  </p>
                )}
                {selectedNodeContext.details && (
                  <pre className="text-[10px] text-white/60 font-mono whitespace-pre-wrap break-words">
                    {JSON.stringify(selectedNodeContext.details, null, 2)}
                  </pre>
                )}
              </div>
            ) : (
              <div className="h-full flex items-center justify-center">
                <div className="text-center">
                  <FileText className="w-12 h-12 text-white/20 mx-auto mb-3" />
                  <p className="text-xs text-white/50 font-mono">NO DOCUMENT</p>
                </div>
              </div>
            )}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
