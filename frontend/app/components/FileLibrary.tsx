"use client";

import { useState, useEffect } from "react";
import { FileText, Upload, Loader2 } from "lucide-react";
import { useAppStore } from "../store/useAppStore";
import { API_ENDPOINTS } from "../lib/constants";
import type { Document } from "../lib/types";

export default function FileLibrary() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const { openPDFViewer } = useAppStore();

  // Fetch documents from graph data
  useEffect(() => {
    const fetchDocuments = async () => {
      try {
        setIsLoading(true);
        const response = await fetch(API_ENDPOINTS.GRAPH);
        if (!response.ok) {
          throw new Error("Failed to fetch graph data");
        }
        const data = await response.json();
        
        // Extract unique Document nodes
        const docMap = new Map<string, Document>();
        if (data.nodes) {
          data.nodes.forEach((node: any) => {
            if (node.label === "Document" && node.id && node.name) {
              if (!docMap.has(node.id)) {
                docMap.set(node.id, {
                  id: node.id,
                  name: node.name,
                });
              }
            }
          });
        }
        
        setDocuments(Array.from(docMap.values()));
      } catch (error) {
        console.error("Error fetching documents:", error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchDocuments();
  }, []);

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    if (!file.type.includes("pdf")) {
      alert("Please upload a PDF file");
      return;
    }

    setIsUploading(true);
    setUploadProgress(0);

    try {
      const formData = new FormData();
      formData.append("file", file);

      const xhr = new XMLHttpRequest();

      xhr.upload.addEventListener("progress", (e) => {
        if (e.lengthComputable) {
          const percentComplete = (e.loaded / e.total) * 100;
          setUploadProgress(percentComplete);
        }
      });

      xhr.addEventListener("load", () => {
        if (xhr.status === 200) {
          const result = JSON.parse(xhr.responseText);
          setDocuments((prev) => [
            ...prev,
            {
              id: result.doc_id,
              name: result.file_name,
              created_at: new Date().toISOString(),
            },
          ]);
          setUploadProgress(100);
          setTimeout(() => {
            setIsUploading(false);
            setUploadProgress(0);
          }, 500);
        } else {
          throw new Error(`Upload failed: ${xhr.statusText}`);
        }
      });

      xhr.addEventListener("error", () => {
        throw new Error("Upload failed");
      });

      xhr.open("POST", API_ENDPOINTS.INGEST);
      xhr.send(formData);
    } catch (error) {
      console.error("Upload error:", error);
      setIsUploading(false);
      setUploadProgress(0);
    }
  };

  const handleDocClick = (doc: Document) => {
    const pdfUrl = API_ENDPOINTS.STATIC(doc.name);
    openPDFViewer(pdfUrl, doc.name, 1);
  };

  return (
    <div className="flex-1 overflow-hidden flex flex-col p-4">
      {/* File List */}
      <div className="flex-1 overflow-y-auto space-y-2 min-h-0">
        {isLoading ? (
          <div className="text-center py-8">
            <Loader2 className="w-5 h-5 text-cyan-400 animate-spin mx-auto mb-2" />
            <p className="text-xs text-white/50 font-mono">LOADING...</p>
          </div>
        ) : documents.length === 0 ? (
          <div className="text-center py-8">
            <p className="text-xs text-white/50 font-mono">NO DOCUMENTS</p>
          </div>
        ) : (
          documents.map((doc) => (
            <div
              key={doc.id}
              onClick={() => handleDocClick(doc)}
              className="flex items-center gap-3 p-3 rounded-lg border border-white/10 bg-black/20 hover:bg-white/5 hover:border-white/15 cursor-pointer transition-all"
            >
              {/* File Icon */}
              <FileText className="w-5 h-5 text-white/60 flex-shrink-0" />

              {/* File Info */}
              <div className="flex-1 min-w-0">
                <p className="text-xs font-mono text-white/90 truncate">{doc.name}</p>
                {doc.created_at && (
                  <p className="text-[10px] text-white/40 font-mono mt-0.5">
                    {new Date(doc.created_at).toLocaleDateString()}
                  </p>
                )}
              </div>
            </div>
          ))
        )}
      </div>

      {/* Upload Button - Holographic Style */}
      <div className="mt-4 pt-4 border-t border-white/10">
        <label className="block cursor-pointer">
          <div className="relative group">
            <div className="absolute inset-0 bg-gradient-to-r from-cyan-500/20 via-purple-500/20 to-cyan-500/20 rounded-xl opacity-0 group-hover:opacity-100 blur-xl transition-opacity" />
            <div className="relative flex items-center justify-center gap-2 px-4 py-3 rounded-xl border border-white/10 bg-black/40 hover:bg-white/5 transition-all group-hover:border-cyan-500/30 group-hover:shadow-[0_0_20px_rgba(0,243,255,0.3)]">
              {isUploading ? (
                <>
                  <Loader2 className="w-4 h-4 text-cyan-400 animate-spin" />
                  <span className="text-xs font-mono text-white/90">
                    UPLOADING {Math.round(uploadProgress)}%
                  </span>
                  {uploadProgress > 0 && (
                    <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-cyan-500/50">
                      <div
                        className="h-full bg-cyan-500 transition-all duration-300"
                        style={{ width: `${uploadProgress}%` }}
                      />
                    </div>
                  )}
                </>
              ) : (
                <>
                  <Upload className="w-4 h-4 text-cyan-400" />
                  <span className="text-xs font-mono text-white/90">UPLOAD DOCUMENT</span>
                </>
              )}
            </div>
          </div>
          <input
            type="file"
            accept=".pdf"
            onChange={handleFileUpload}
            className="hidden"
            disabled={isUploading}
          />
        </label>
      </div>
    </div>
  );
}
