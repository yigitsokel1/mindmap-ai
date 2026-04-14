"use client";

import { useState, useEffect } from "react";
import { API_ENDPOINTS } from "../lib/constants";

interface SystemStatus {
  neo4j: boolean;
  graph: boolean;
  engine: boolean;
}

export default function StatusBar() {
  const [status, setStatus] = useState<SystemStatus>({
    neo4j: false,
    graph: false,
    engine: true, // Always true - client-side
  });

  useEffect(() => {
    const checkStatus = async () => {
      try {
        // Check Neo4j and Graph status by fetching graph data
        const response = await fetch(API_ENDPOINTS.GRAPH);
        const isHealthy = response.ok;
        
        setStatus({
          neo4j: isHealthy,
          graph: isHealthy,
          engine: true,
        });
      } catch (error) {
        setStatus({
          neo4j: false,
          graph: false,
          engine: true,
        });
      }
    };

    checkStatus();
    const interval = setInterval(checkStatus, 10000); // Check every 10 seconds

    return () => clearInterval(interval);
  }, []);

  return (
    <div className="fixed bottom-4 left-1/2 -translate-x-1/2 z-20 flex items-center gap-4 px-4 py-2 bg-black/40 backdrop-blur-2xl border border-white/10 rounded-full shadow-[0_8px_32px_rgba(0,0,0,0.6)]">
      {/* System Status Indicators */}
      <div className="flex items-center gap-2">
        <div
          className={`w-2 h-2 rounded-full ${
            status.neo4j ? "bg-green-500 animate-pulse" : "bg-red-500"
          }`}
        />
        <span className="text-[10px] font-mono text-white/70">Neo4j</span>
      </div>
      <div className="w-px h-4 bg-white/10" />
      <div className="flex items-center gap-2">
        <div
          className={`w-2 h-2 rounded-full ${
            status.graph ? "bg-green-500 animate-pulse" : "bg-red-500"
          }`}
        />
        <span className="text-[10px] font-mono text-white/70">Graph Active</span>
      </div>
      <div className="w-px h-4 bg-white/10" />
      <div className="flex items-center gap-2">
        <div
          className={`w-2 h-2 rounded-full ${
            status.engine ? "bg-green-500 animate-pulse" : "bg-red-500"
          }`}
        />
        <span className="text-[10px] font-mono text-white/70">3D Engine Ready</span>
      </div>
    </div>
  );
}
