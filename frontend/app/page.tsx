"use client";

import { useEffect, useRef, useState } from "react";
import dynamic from "next/dynamic";

// Dynamically import ForceGraph2D with SSR disabled
const ForceGraph2D = dynamic(
  () => import("react-force-graph-2d"),
  { ssr: false }
);

interface GraphNode {
  id: string;
  label: string;
  name: string;
}

interface GraphLink {
  source: string;
  target: string;
  type: string;
}

interface GraphData {
  nodes: GraphNode[];
  links: GraphLink[];
}

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  relatedNodeIds?: string[];
}

// Component for displaying long text with "Read More" functionality
const LongTextContent = ({ text }: { text: string }) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const maxLength = 150;
  
  if (text.length <= maxLength) {
    return (
      <p className="text-sm text-gray-200 break-words leading-relaxed">
        {text}
      </p>
    );
  }

  return (
    <div>
      <p className="text-sm text-gray-200 break-words leading-relaxed">
        {isExpanded ? text : `${text.substring(0, maxLength)}...`}
      </p>
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="mt-2 text-xs text-blue-400 hover:text-blue-300 transition-colors underline"
      >
        {isExpanded ? "Read Less" : "Read More"}
      </button>
    </div>
  );
};

export default function Home() {
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputMessage, setInputMessage] = useState("");
  const [isLoadingResponse, setIsLoadingResponse] = useState(false);
  const [highlightedNodeIds, setHighlightedNodeIds] = useState<Set<string>>(new Set());
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [isChatOpen, setIsChatOpen] = useState(true);
  const graphRef = useRef<any>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    const fetchGraphData = async () => {
      try {
        setLoading(true);
        setError(null);
        const response = await fetch("http://localhost:8000/api/graph");
        
        if (!response.ok) {
          throw new Error(`Failed to fetch graph data: ${response.statusText}`);
        }
        
        const data = await response.json();
        
        // Debug: Check node structure
        if (data.nodes && data.nodes.length > 0) {
          const sampleNode = data.nodes[0];
          console.log("Sample node from API:", sampleNode);
          console.log("Sample node keys:", Object.keys(sampleNode));
          console.log("Sample node full structure:", JSON.stringify(sampleNode, null, 2));
          
          // Check a Paper node specifically if available
          const paperNode = data.nodes.find((n: GraphNode) => n.label === "Paper");
          if (paperNode) {
            console.log("Paper node found:", paperNode);
            console.log("Paper node keys:", Object.keys(paperNode));
            console.log("Paper node full:", JSON.stringify(paperNode, null, 2));
          }
          
          // Also check a Concept node
          const conceptNode = data.nodes.find((n: GraphNode) => n.label === "Concept");
          if (conceptNode) {
            console.log("Concept node found:", conceptNode);
            console.log("Concept node keys:", Object.keys(conceptNode));
          }
        }
        
        setGraphData(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unknown error occurred");
        console.error("Error fetching graph data:", err);
      } finally {
        setLoading(false);
      }
    };

    fetchGraphData();
  }, []);

  const handleSendMessage = async () => {
    if (!inputMessage.trim() || isLoadingResponse) return;

    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      role: "user",
      content: inputMessage.trim(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputMessage("");
    setIsLoadingResponse(true);

    try {
      const response = await fetch("http://localhost:8000/api/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ question: userMessage.content }),
      });

      if (!response.ok) {
        throw new Error(`Failed to get response: ${response.statusText}`);
      }

      const data = await response.json();
      
      const assistantMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: data.result || "No response received",
        relatedNodeIds: data.related_node_ids || [],
      };

      setMessages((prev) => [...prev, assistantMessage]);

      // Highlight nodes based on related_node_ids
      if (data.related_node_ids && data.related_node_ids.length > 0) {
        console.log("Received node IDs from API:", data.related_node_ids);
        
        // Ensure all IDs are strings for comparison
        const nodeIdSet = new Set(data.related_node_ids.map((id: any) => String(id)));
        
        // Check link source/target formats for debugging
        if (graphData?.links && graphData.links.length > 0) {
          const sampleLink = graphData.links[0];
          console.log("Sample link format:", {
            source: sampleLink.source,
            sourceType: typeof sampleLink.source,
            target: sampleLink.target,
            targetType: typeof sampleLink.target
          });
          
          // Check if any links connect highlighted nodes
          const linksBetweenHighlighted = graphData.links.filter((link: GraphLink) => {
            const sourceId = String(typeof link.source === 'string' ? link.source : (link.source as any)?.id || link.source);
            const targetId = String(typeof link.target === 'string' ? link.target : (link.target as any)?.id || link.target);
            return nodeIdSet.has(sourceId) && nodeIdSet.has(targetId);
          });
          console.log(`Found ${linksBetweenHighlighted.length} links between highlighted nodes out of ${graphData.links.length} total links`);
        }
        
        // Check which nodes are missing from current graph data
        const existingNodeIds = new Set(graphData?.nodes.map(n => String(n.id)) || []);
        const missingNodeIds = data.related_node_ids.filter((id: string) => !existingNodeIds.has(String(id)));
        
        // If there are missing nodes, fetch them from the API
        if (missingNodeIds.length > 0 && graphData) {
          console.log(`Missing ${missingNodeIds.length} nodes, fetching...`, missingNodeIds);
          
          // Fetch missing nodes and their relationships
          const nodeIdsParam = missingNodeIds.join(",");
          console.log(`Fetching from API: /api/graph?node_ids=${nodeIdsParam.substring(0, 100)}...`);
          
          fetch(`http://localhost:8000/api/graph?node_ids=${encodeURIComponent(nodeIdsParam)}`)
            .then(res => {
              console.log(`API response status: ${res.status}`);
              if (!res.ok) {
                throw new Error(`API returned ${res.status}: ${res.statusText}`);
              }
              return res.json();
            })
            .then(additionalData => {
              console.log(`API returned: ${additionalData.nodes?.length || 0} nodes, ${additionalData.links?.length || 0} links`);
              
              if (additionalData.nodes && additionalData.links) {
                // Merge new nodes and links with existing graph data
                const mergedNodes = [...graphData.nodes];
                const mergedLinks = [...graphData.links];
                const existingIds = new Set(graphData.nodes.map(n => n.id));
                
                // Add new nodes
                let addedNodes = 0;
                additionalData.nodes.forEach((node: GraphNode) => {
                  if (!existingIds.has(node.id)) {
                    mergedNodes.push(node);
                    addedNodes++;
                  }
                });
                
                // Add new links (avoid duplicates)
                const existingLinkKeys = new Set(
                  graphData.links.map(l => `${l.source}-${l.target}-${l.type}`)
                );
                let addedLinks = 0;
                additionalData.links.forEach((link: GraphLink) => {
                  const linkKey = `${link.source}-${link.target}-${link.type}`;
                  if (!existingLinkKeys.has(linkKey)) {
                    mergedLinks.push(link);
                    addedLinks++;
                  }
                });
                
                setGraphData({
                  nodes: mergedNodes,
                  links: mergedLinks
                });
                console.log(`Added ${addedNodes} nodes and ${addedLinks} links to graph`);
              } else {
                console.warn("API returned data but no nodes/links found:", additionalData);
              }
            })
            .catch(err => {
              console.error("Error fetching missing nodes:", err);
            });
        }
        
        setHighlightedNodeIds(nodeIdSet);
        
        // Check for matches after potential merge
        setTimeout(() => {
          const currentGraphNodes = graphData?.nodes || [];
          const matchingNodes = currentGraphNodes.filter(n => nodeIdSet.has(String(n.id)));
          console.log(`Found ${matchingNodes.length} matching nodes out of ${data.related_node_ids.length} highlighted IDs after merge`);
        }, 500);
      }
    } catch (err) {
      const errorMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: `Error: ${err instanceof Error ? err.message : "Unknown error occurred"}`,
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoadingResponse(false);
    }
  };

  const handleResetView = () => {
    setHighlightedNodeIds(new Set());
    setSelectedNode(null);
  };

  const handleNodeClick = (node: GraphNode) => {
    // ForceGraph2D may mutate nodes with physics properties (x, y, vx, vy, etc.)
    // So we should find the original node from graphData to preserve all properties
    const nodeIdStr = String(node.id);
    const originalNode = graphData?.nodes.find(n => String(n.id) === nodeIdStr);
    
    if (originalNode) {
      console.log("Original node from graphData:", originalNode);
      console.log("Original node keys:", Object.keys(originalNode));
      console.log("Clicked node (may be mutated):", node);
      console.log("Clicked node keys:", Object.keys(node));
      setSelectedNode(originalNode);
    } else {
      console.warn("Could not find original node in graphData, using clicked node");
      setSelectedNode(node);
    }
    
    // Center camera on the clicked node
    if (graphRef.current) {
      graphRef.current.centerAt(node.x || 0, node.y || 0, 1000); // 1000ms animation
      graphRef.current.zoom(2, 1000); // Zoom in slightly
    }
  };

  const handleCloseInspector = () => {
    setSelectedNode(null);
  };

  const handleKeyPress = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  // Node styling based on highlight state and selection
  const getNodeColor = (node: GraphNode) => {
    const nodeIdStr = String(node.id);
    
    // Selected node takes priority - yellow
    if (selectedNode && String(selectedNode.id) === nodeIdStr) {
      return "#eab308"; // Yellow for selected node
    }
    
    // Chat highlighted nodes - green
    if (highlightedNodeIds.has(nodeIdStr)) {
      return "#22c55e"; // Green for highlighted
    }
    
    // If there are any highlights active, dim non-highlighted nodes
    if (highlightedNodeIds.size > 0) {
      return "#333333"; // Dimmed for non-highlighted when there are highlights
    }
    
    // No highlights active - use auto-coloring by label
    return null; // ForceGraph2D will use nodeAutoColorBy when nodeColor returns null
  };

  const getNodeSize = (node: GraphNode) => {
    const nodeIdStr = String(node.id);
    
    // Selected node is largest
    if (selectedNode && String(selectedNode.id) === nodeIdStr) {
      return 12; // Largest for selected node
    }
    
    // Chat highlighted nodes
    if (highlightedNodeIds.has(nodeIdStr)) {
      return 10; // Larger for highlighted
    }
    
    if (highlightedNodeIds.size > 0) {
      return 4; // Smaller for dimmed
    }
    return 6; // Default size
  };

  // Link styling based on highlight state
  const getLinkOpacity = (link: GraphLink) => {
    if (highlightedNodeIds.size === 0) {
      return 0.8; // Higher default opacity
    }
    
    // Link source/target can be string ID or node object - normalize to string
    const sourceId = typeof link.source === 'string' ? link.source : String((link.source as any)?.id || link.source);
    const targetId = typeof link.target === 'string' ? link.target : String((link.target as any)?.id || link.target);
    
    // Debug: Log first few links to see format
    if (highlightedNodeIds.size > 0) {
      const sourceHighlighted = highlightedNodeIds.has(sourceId);
      const targetHighlighted = highlightedNodeIds.has(targetId);
      
      if (sourceHighlighted && targetHighlighted) {
        return 1.0; // Full opacity for links between highlighted nodes
      } else if (sourceHighlighted || targetHighlighted) {
        return 0.7; // Higher opacity for links from/to highlighted nodes
      } else {
        return 0.15; // Slightly higher for other links so they're still visible
      }
    }
    
    return 0.8;
  };

  const getLinkColor = (link: GraphLink) => {
    if (highlightedNodeIds.size === 0) {
      return "#94a3b8"; // Lighter default color for better visibility
    }
    
    // Link source/target can be string ID or node object - normalize to string
    const sourceId = typeof link.source === 'string' ? link.source : String((link.source as any)?.id || link.source);
    const targetId = typeof link.target === 'string' ? link.target : String((link.target as any)?.id || link.target);
    
    // Check if both source and target nodes are highlighted
    const sourceHighlighted = highlightedNodeIds.has(sourceId);
    const targetHighlighted = highlightedNodeIds.has(targetId);
    
    if (sourceHighlighted && targetHighlighted) {
      return "#22c55e"; // Bright green for links between highlighted nodes
    } else if (sourceHighlighted || targetHighlighted) {
      return "#86efac"; // Light green for links from/to highlighted nodes
    } else {
      return "#475569"; // Darker gray but still visible for other links
    }
  };

  const getLinkWidth = (link: GraphLink) => {
    if (highlightedNodeIds.size === 0) {
      return 1.5; // Slightly thicker default
    }
    
    // Link source/target can be string ID or node object - normalize to string
    const sourceId = typeof link.source === 'string' ? link.source : String((link.source as any)?.id || link.source);
    const targetId = typeof link.target === 'string' ? link.target : String((link.target as any)?.id || link.target);
    
    // Check if both source and target nodes are highlighted
    const sourceHighlighted = highlightedNodeIds.has(sourceId);
    const targetHighlighted = highlightedNodeIds.has(targetId);
    
    if (sourceHighlighted && targetHighlighted) {
      return 5; // Much thicker for links between highlighted nodes
    } else if (sourceHighlighted || targetHighlighted) {
      return 3; // Thicker for links from/to highlighted nodes
    } else {
      return 1; // Thinner but still visible for other links
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-black text-white">
        <div className="text-center">
          <div className="mb-4 text-lg">Loading graph data...</div>
          <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-white border-r-transparent"></div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-black text-white">
        <div className="text-center">
          <div className="mb-4 text-lg text-red-500">Error: {error}</div>
          <button
            onClick={() => window.location.reload()}
            className="rounded bg-white px-4 py-2 text-black hover:bg-gray-200"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (!graphData || !graphData.nodes || graphData.nodes.length === 0) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-black text-white">
        <div className="text-center">
          <div className="mb-4 text-lg">No graph data available</div>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 bg-black relative">
      {/* Graph Visualization */}
      <ForceGraph2D
        ref={graphRef}
        graphData={graphData}
        nodeAutoColorBy={highlightedNodeIds.size === 0 && !selectedNode ? "label" : null}
        nodeColor={getNodeColor}
        nodeVal={getNodeSize}
        linkOpacity={getLinkOpacity}
        linkColor={getLinkColor}
        linkWidth={getLinkWidth}
        linkDirectionalArrowLength={6}
        linkDirectionalArrowRelPos={1}
        linkCurvature={0.25}
        nodeLabel={(node: GraphNode) => `${node.name} (${node.label})`}
        linkLabel={(link: GraphLink) => link.type}
        backgroundColor="#000000"
        width={typeof window !== "undefined" ? window.innerWidth : 800}
        height={typeof window !== "undefined" ? window.innerHeight : 600}
        cooldownTicks={100}
        onNodeClick={handleNodeClick}
        onNodeHover={(node) => {
          if (node) {
            const isHighlighted = highlightedNodeIds.has(String(node.id));
            console.log(`Node hover: ${node.name}, highlighted: ${isHighlighted}, ID: ${node.id}`);
          }
        }}
      />

      {/* Reset View Button - Only show when there are highlights but no selected node */}
      {highlightedNodeIds.size > 0 && !selectedNode && (
        <button
          onClick={handleResetView}
          className="fixed top-4 left-4 z-20 rounded-lg bg-blue-600 px-4 py-2 text-white shadow-lg hover:bg-blue-700 transition-colors"
        >
          Reset View
        </button>
      )}

      {/* Node Inspector Panel */}
      {selectedNode && (
        <div className="fixed top-4 left-4 z-30 w-96 max-h-[80vh] overflow-y-auto bg-gray-900/90 backdrop-blur-md border border-gray-700 rounded-lg shadow-2xl p-6 text-white">
          {/* Header */}
          <div className="flex items-start justify-between mb-4">
            <h3 className="text-xl font-bold text-white">Node Inspector</h3>
            <button
              onClick={handleCloseInspector}
              className="text-gray-400 hover:text-white transition-colors text-xl leading-none"
              aria-label="Close"
            >
              ✕
            </button>
          </div>

          {/* Node Label/Type (Badge) - At the top */}
          {selectedNode.label && (
            <div className="mb-3">
              <span className="inline-block px-3 py-1 bg-blue-600/80 text-blue-100 rounded-full text-sm font-medium">
                {selectedNode.label}
              </span>
            </div>
          )}

          {/* Node Name (Main Title) */}
          <h2 className="text-2xl font-semibold text-white mb-4 break-words">
            {selectedNode.name || selectedNode.id}
          </h2>

          {/* Divider */}
          <div className="border-t border-gray-700 my-4"></div>

          {/* Academic Properties */}
          {(() => {
            // Filter out technical/physics engine keys
            const technicalKeys = ['id', 'x', 'y', 'vx', 'vy', 'fx', 'fy', 'index', 'color', '__indexColor', 'name', 'label'];
            
            // Get academic properties (exclude technical keys)
            const academicProperties = Object.entries(selectedNode).filter(([key, value]) => {
              return !technicalKeys.includes(key) && value !== null && value !== undefined && value !== '';
            });

            // If no academic properties, show connection information instead
            if (academicProperties.length === 0) {
              // Get connections for this node
              const connections = graphData?.links.filter(
                (link) => {
                  const sourceId = typeof link.source === 'string' ? link.source : String((link.source as any)?.id || link.source);
                  const targetId = typeof link.target === 'string' ? link.target : String((link.target as any)?.id || link.target);
                  return sourceId === String(selectedNode.id) || targetId === String(selectedNode.id);
                }
              ) || [];

              // Get connected node IDs
              const connectedNodeIds = new Set<string>();
              connections.forEach((link) => {
                const sourceId = typeof link.source === 'string' ? link.source : String((link.source as any)?.id || link.source);
                const targetId = typeof link.target === 'string' ? link.target : String((link.target as any)?.id || link.target);
                if (sourceId === String(selectedNode.id)) {
                  connectedNodeIds.add(targetId);
                } else {
                  connectedNodeIds.add(sourceId);
                }
              });

              // Get connected node names
              const connectedNodes = Array.from(connectedNodeIds)
                .map(nodeId => graphData?.nodes.find(n => String(n.id) === nodeId))
                .filter(Boolean) as GraphNode[];

              if (connectedNodes.length > 0) {
                // Group connections by relationship type
                const connectionsByType = new Map<string, { nodes: GraphNode[], count: number }>();
                connections.forEach((link) => {
                  const type = link.type;
                  if (!connectionsByType.has(type)) {
                    connectionsByType.set(type, { nodes: [], count: 0 });
                  }
                  connectionsByType.get(type)!.count++;
                });

                return (
                  <div className="space-y-4">
                    <div className="text-sm text-gray-400 italic mb-3">
                      This node doesn't have additional metadata properties stored in the database.
                    </div>
                    
                    {connectionsByType.size > 0 && (
                      <div>
                        <div className="text-xs text-gray-400 uppercase tracking-wide mb-2">
                          Relationship Types
                        </div>
                        <div className="space-y-1">
                          {Array.from(connectionsByType.entries()).map(([type, data]) => (
                            <div key={type} className="text-sm text-gray-300">
                              <span className="text-blue-400 font-medium">{type}</span>
                              <span className="text-gray-500 ml-2">({data.count} connection{data.count !== 1 ? 's' : ''})</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {connectedNodes.length > 0 && connectedNodes.length <= 10 && (
                      <div>
                        <div className="text-xs text-gray-400 uppercase tracking-wide mb-2">
                          Connected Nodes ({connectedNodes.length})
                        </div>
                        <div className="space-y-1 max-h-40 overflow-y-auto">
                          {connectedNodes.slice(0, 10).map((node) => (
                            <div key={node.id} className="text-sm text-gray-300 truncate">
                              • {node.name} <span className="text-gray-500 text-xs">({node.label})</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                );
              }

              return (
                <div className="text-sm text-gray-400 italic">
                  No additional metadata available.
                </div>
              );
            }

            // Helper function to format key names
            const formatKey = (key: string): string => {
              return key
                .replace(/_/g, ' ')
                .replace(/([A-Z])/g, ' $1')
                .split(' ')
                .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
                .join(' ')
                .trim();
            };

            // Helper function to check if text is long
            const isLongText = (text: string): boolean => {
              return text.length > 150;
            };

            return (
              <div className="space-y-4">
                {academicProperties.map(([key, value]) => {
                  const displayKey = formatKey(key);
                  const valueStr = typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value);
                  const isLong = isLongText(valueStr);
                  
                  return (
                    <div key={key} className="border-b border-gray-800 pb-3 last:border-0">
                      <div className="text-xs text-gray-400 uppercase tracking-wide mb-1.5">
                        {displayKey}
                      </div>
                      {isLong ? (
                        <LongTextContent text={valueStr} />
                      ) : (
                        <p className="text-sm text-gray-200 break-words leading-relaxed">
                          {valueStr}
                        </p>
                      )}
                    </div>
                  );
                })}
              </div>
            );
          })()}

          {/* Connection Info (if available in graph) */}
          {graphData && (
            <>
              <div className="border-t border-gray-700 my-4"></div>
              <div className="space-y-2">
                <div>
                  <span className="text-xs text-gray-400 uppercase tracking-wide">Connections</span>
                  <div className="mt-2">
                    {(() => {
                      const connections = graphData.links.filter(
                        (link) => {
                          const sourceId = typeof link.source === 'string' ? link.source : String((link.source as any)?.id || link.source);
                          const targetId = typeof link.target === 'string' ? link.target : String((link.target as any)?.id || link.target);
                          return sourceId === String(selectedNode.id) || targetId === String(selectedNode.id);
                        }
                      );
                      
                      if (connections.length === 0) {
                        return (
                          <p className="text-sm text-gray-400 italic">No connections found</p>
                        );
                      }
                      
                      return (
                        <p className="text-sm text-gray-200">
                          Connected to <strong className="text-white font-semibold">{connections.length}</strong> node(s)
                        </p>
                      );
                    })()}
                  </div>
                </div>
              </div>
            </>
          )}
        </div>
      )}

      {/* Chat Interface */}
      <div
        className={`fixed right-0 top-0 h-full w-96 bg-gray-900 text-white shadow-2xl transform transition-transform duration-300 z-30 ${
          isChatOpen ? "translate-x-0" : "translate-x-full"
        }`}
      >
        {/* Chat Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-700 bg-gray-800">
          <h2 className="text-lg font-semibold">Chat with GraphRAG</h2>
          <button
            onClick={() => setIsChatOpen(!isChatOpen)}
            className="text-gray-400 hover:text-white"
          >
            {isChatOpen ? "✕" : "☰"}
          </button>
        </div>

        {/* Messages Container */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4 h-[calc(100%-140px)]">
          {messages.length === 0 && (
            <div className="text-center text-gray-400 mt-8">
              <p>Ask a question about the knowledge graph!</p>
              <p className="text-sm mt-2">Example: "How are attention mechanisms related to recurrent models?"</p>
            </div>
          )}
          {messages.map((message) => (
            <div
              key={message.id}
              className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`max-w-[80%] rounded-lg px-4 py-2 ${
                  message.role === "user"
                    ? "bg-blue-600 text-white"
                    : "bg-gray-700 text-gray-100"
                }`}
              >
                <p className="whitespace-pre-wrap break-words">{message.content}</p>
                {message.relatedNodeIds && message.relatedNodeIds.length > 0 && (
                  <p className="text-xs mt-2 opacity-75">
                    Highlighted {message.relatedNodeIds.length} node(s)
                  </p>
                )}
              </div>
            </div>
          ))}
          {isLoadingResponse && (
            <div className="flex justify-start">
              <div className="bg-gray-700 rounded-lg px-4 py-2">
                <div className="flex space-x-2">
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "0.2s" }}></div>
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "0.4s" }}></div>
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input Area */}
        <div className="p-4 border-t border-gray-700 bg-gray-800">
          <div className="flex space-x-2">
            <input
              type="text"
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Ask a question..."
              disabled={isLoadingResponse}
              className="flex-1 rounded-lg bg-gray-700 px-4 py-2 text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
            />
            <button
              onClick={handleSendMessage}
              disabled={!inputMessage.trim() || isLoadingResponse}
              className="rounded-lg bg-blue-600 px-4 py-2 text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              Send
            </button>
          </div>
        </div>
      </div>

      {/* Chat Toggle Button (when closed) */}
      {!isChatOpen && (
        <button
          onClick={() => setIsChatOpen(true)}
          className="fixed right-4 top-4 z-20 rounded-full bg-blue-600 p-3 text-white shadow-lg hover:bg-blue-700 transition-colors"
          title="Open Chat"
        >
          💬
        </button>
      )}
    </div>
  );
}
