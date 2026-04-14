'use client';

import { useEffect, useRef, useMemo, useState } from 'react';
import ForceGraph3D from 'react-force-graph-3d';
import * as THREE from 'three';
import { useAppStore } from '../store/useAppStore';
import { API_ENDPOINTS } from '../lib/constants';
import type { GraphNode, GraphLink, GraphData } from '../lib/types';

// Helper function to create glow texture (outside component to prevent recreation)
const createGlowTexture = (): THREE.Texture | null => {
  if (typeof document === 'undefined') {
    return null;
  }
  
  const canvas = document.createElement('canvas');
  canvas.width = 64;
  canvas.height = 64;
  const ctx = canvas.getContext('2d');
  if (!ctx) return null;
  
  // Create radial gradient for glow effect
  const gradient = ctx.createRadialGradient(32, 32, 0, 32, 32, 32);
  gradient.addColorStop(0, 'rgba(255, 255, 255, 1)');
  gradient.addColorStop(0.2, 'rgba(200, 220, 255, 0.8)');
  gradient.addColorStop(0.5, 'rgba(100, 150, 255, 0.4)');
  gradient.addColorStop(1, 'rgba(0, 0, 0, 0)');
  
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, 64, 64);
  
  const texture = new THREE.Texture(canvas);
  texture.needsUpdate = true;
  return texture;
};

export default function GraphViewer3D() {
  const graphRef = useRef<any>(null);
  const [graphData, setGraphData] = useState<GraphData>({ nodes: [], links: [] });
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const highlightedNodeIds = useAppStore((state) => state.highlightedNodeIds);
  const previousHighlightedRef = useRef<string[]>([]);
  const starfieldRef = useRef<THREE.Points | null>(null);
  const starsGeometryRef = useRef<THREE.BufferGeometry | null>(null);
  const starsMaterialRef = useRef<THREE.PointsMaterial | null>(null);
  const isInitializedRef = useRef(false);
  const [isAnimating, setIsAnimating] = useState(false);
  const animationTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const mountRef = useRef(false);
  const waitForStablePositionRef = useRef<number | null>(null);
  const nodePositionsRef = useRef<Map<string, { x: number; y: number; z: number }>>(new Map());
  const [autoRotateEnabled, setAutoRotateEnabled] = useState(true);
  const starfieldAnimationRef = useRef<number | null>(null);
  const nodeInitialPositionsRef = useRef<Map<string, { x: number; y: number; z: number }>>(new Map());
  const activeTargetNodeRef = useRef<{ id: string; label: string; distance: number } | null>(null);
  const focusPeriodActiveRef = useRef(false);
  const lockedTargetPositionRef = useRef<{ x: number; y: number; z: number } | null>(null);

  // Memoize glow texture - created once and reused
  const glowTexture = useMemo(() => createGlowTexture(), []);

  // Fetch graph data from API - only once
  useEffect(() => {
    if (mountRef.current) return;
    mountRef.current = true;
    
    const fetchGraphData = async () => {
      try {
        setIsLoading(true);
        setError(null);
        const response = await fetch(API_ENDPOINTS.GRAPH);
        
        if (!response.ok) {
          throw new Error(`Failed to fetch graph: ${response.statusText}`);
        }
        
        const data = await response.json();
        console.log('Graph data loaded:', {
          nodes: data.nodes?.length || 0,
          links: data.links?.length || 0,
          documents: data.nodes?.filter((n: any) => n.label === 'Document').length || 0,
          chunks: data.nodes?.filter((n: any) => n.label === 'Chunk').length || 0,
        });
        
        // Store initial node positions to prevent drift
        if (data.nodes) {
          nodeInitialPositionsRef.current.clear();
          data.nodes.forEach((node: any) => {
            if (node.x !== undefined && node.y !== undefined && node.z !== undefined) {
              nodeInitialPositionsRef.current.set(node.id, {
                x: node.x,
                y: node.y,
                z: node.z,
              });
            }
          });
        }
        
        setGraphData(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
        console.error('Error fetching graph data:', err);
      } finally {
        setIsLoading(false);
      }
    };

    fetchGraphData();
  }, []);

  // Add starfield background - only once, with proper cleanup
  useEffect(() => {
    if (!graphRef.current || isLoading || isInitializedRef.current) return;

    const scene = graphRef.current.scene();
    if (!scene) return;

    // Create starfield with 5000 points
    const starsGeometry = new THREE.BufferGeometry();
    const starsCount = 5000;
    const positions = new Float32Array(starsCount * 3);

    for (let i = 0; i < starsCount * 3; i += 3) {
      const radius = 2000 + Math.random() * 3000;
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(Math.random() * 2 - 1);
      
      positions[i] = radius * Math.sin(phi) * Math.cos(theta);
      positions[i + 1] = radius * Math.sin(phi) * Math.sin(theta);
      positions[i + 2] = radius * Math.cos(phi);
    }

    starsGeometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));

    const starsMaterial = new THREE.PointsMaterial({
      color: 0xffffff,
      size: 0.5,
      transparent: true,
      opacity: 0.6,
    });

    const starfield = new THREE.Points(starsGeometry, starsMaterial);
    scene.add(starfield);
    
    starfieldRef.current = starfield;
    starsGeometryRef.current = starsGeometry;
    starsMaterialRef.current = starsMaterial;
    isInitializedRef.current = true;

    // Starfield Animation Loop - Warp Effect
    const animateStarfield = () => {
      if (!starfieldRef.current) return;
      
      const positions = starsGeometryRef.current?.getAttribute('position') as THREE.BufferAttribute;
      if (!positions) return;
      
      const positionsArray = positions.array as Float32Array;
      const starfieldSpeed = 0.05; // Warp speed - very slow drift
      const resetDistance = -5000; // Reset stars that go too far
      
      for (let i = 2; i < positionsArray.length; i += 3) {
        // Move each star towards camera (negative Z)
        positionsArray[i] -= starfieldSpeed;
        
        // Reset star if it goes too far
        if (positionsArray[i] < resetDistance) {
          // Reset to far back
          const radius = 2000 + Math.random() * 3000;
          const theta = Math.random() * Math.PI * 2;
          const phi = Math.acos(Math.random() * 2 - 1);
          
          positionsArray[i - 2] = radius * Math.sin(phi) * Math.cos(theta);
          positionsArray[i - 1] = radius * Math.sin(phi) * Math.sin(theta);
          positionsArray[i] = radius * Math.cos(phi);
        }
      }
      
      positions.needsUpdate = true;
      starfieldAnimationRef.current = requestAnimationFrame(animateStarfield);
    };
    
    // Start animation loop
    starfieldAnimationRef.current = requestAnimationFrame(animateStarfield);

    return () => {
      // Stop animation loop
      if (starfieldAnimationRef.current !== null) {
        cancelAnimationFrame(starfieldAnimationRef.current);
        starfieldAnimationRef.current = null;
      }
      
      if (starfieldRef.current && scene) {
        scene.remove(starfieldRef.current);
        starfieldRef.current = null;
      }
      if (starsGeometryRef.current) {
        starsGeometryRef.current.dispose();
        starsGeometryRef.current = null;
      }
      if (starsMaterialRef.current) {
        starsMaterialRef.current.dispose();
        starsMaterialRef.current = null;
      }
      isInitializedRef.current = false;
    };
  }, [isLoading]);

  // Handle camera fly to highlighted nodes
  useEffect(() => {
      console.log('[GraphViewer3D] Highlighted nodes effect triggered:', {
        highlightedNodeIds,
        highlightedNodeIdsCount: highlightedNodeIds.length,
        highlightedNodeIdsSample: highlightedNodeIds.slice(0, 3).map(id => id.substring(0, 30) + '...'),
        isLoading,
        isAnimating,
        hasGraphRef: !!graphRef.current,
        graphNodesCount: graphData?.nodes?.length || 0
      });
    
    if (!graphRef.current || highlightedNodeIds.length === 0 || isLoading || isAnimating) {
      if (!graphRef.current) console.log('[GraphViewer3D] No graph ref, skipping');
      if (highlightedNodeIds.length === 0) console.log('[GraphViewer3D] No highlighted nodes, skipping');
      if (isLoading) console.log('[GraphViewer3D] Still loading, skipping');
      if (isAnimating) console.log('[GraphViewer3D] Already animating, skipping');
      return;
    }
    
    const hasChanged = 
      highlightedNodeIds.length !== previousHighlightedRef.current.length ||
      highlightedNodeIds.some((id, idx) => id !== previousHighlightedRef.current[idx]);
    
    if (!hasChanged) {
      console.log('[GraphViewer3D] Highlighted nodes unchanged, skipping');
      return;
    }
    
    console.log('[GraphViewer3D] Highlighted nodes changed, starting animation');
    
    // ========================================
    // STEP 3: STATE RESET (Every Search)
    // ========================================
    // CRITICAL: Complete state reset for each search - prevents conflicts
    // This ensures every search starts from a clean slate
    
    // STEP 3.1: Disable autorotate FIRST (before clearing refs)
    // This prevents autorotate from interfering with new animation
    setAutoRotateEnabled(false);
    
    // STEP 3.2: Disable autorotate in controls immediately
    // This prevents controls from continuing to rotate during new animation
    try {
      const controls = graphRef.current?.controls();
      if (controls) {
        controls.autoRotate = false;
        controls.update();
      }
    } catch (e) {
      // Ignore errors - controls might not be ready
    }
    
    // STEP 3.3: Clear ALL tracking refs - fresh start for new animation
    // IMPORTANT: lockedTargetPositionRef cleared AFTER autorotate is disabled
    // This prevents onEngineTick from using old position
    lockedTargetPositionRef.current = null;
    activeTargetNodeRef.current = null;
    focusPeriodActiveRef.current = false;
    
    // STEP 3.4: Cancel any pending operations from previous search
    if (waitForStablePositionRef.current !== null) {
      cancelAnimationFrame(waitForStablePositionRef.current);
      waitForStablePositionRef.current = null;
    }
    
    if (animationTimeoutRef.current) {
      clearTimeout(animationTimeoutRef.current);
      animationTimeoutRef.current = null;
    }
    
    // STEP 3.5: Update state flags
    previousHighlightedRef.current = [...highlightedNodeIds];
    setIsAnimating(true);
    
    console.log('[GraphViewer3D] ✓ State reset complete, starting fresh animation');
    
    // ========================================
    // STEP 4: FLY TO NODE FUNCTION (Safety & Validation)
    // ========================================
    // Define flyToNode function with comprehensive safety checks
    // This ensures robust operation across all searches
    const flyToNode = (node: GraphNode, x: number, y: number, z: number) => {
      // STEP 4.1: Validate inputs
      if (!node || !node.id) {
        console.error('[GraphViewer3D] Invalid node in flyToNode:', node);
        setIsAnimating(false);
        setAutoRotateEnabled(true);
        return;
      }
      
      // STEP 4.2: Validate position (not all zeros or NaN)
      const isValidPos = 
        (x !== 0 || y !== 0 || z !== 0) && 
        !isNaN(x) && !isNaN(y) && !isNaN(z) &&
        isFinite(x) && isFinite(y) && isFinite(z);
      
      if (!isValidPos) {
        console.warn('[GraphViewer3D] Invalid position in flyToNode:', { x, y, z, nodeId: node.id });
        // Try to get position from cache as fallback
        const cachedPos = nodePositionsRef.current.get(node.id);
        if (cachedPos && (cachedPos.x !== 0 || cachedPos.y !== 0 || cachedPos.z !== 0)) {
          console.log('[GraphViewer3D] Using cached position as fallback');
          flyToNode(node, cachedPos.x, cachedPos.y, cachedPos.z);
          return;
        } else {
          console.error('[GraphViewer3D] No valid position available, aborting animation');
          setIsAnimating(false);
          setAutoRotateEnabled(true);
          return;
        }
      }
      
      // STEP 4.3: Validate graph ref
      if (!graphRef.current) {
        console.warn('[GraphViewer3D] Graph ref is null in flyToNode');
        setIsAnimating(false);
        setAutoRotateEnabled(true);
        return;
      }
      
      console.log('[GraphViewer3D] flyToNode called with:', {
        nodeId: node.id.substring(0, 50) + '...',
        nodeLabel: node.label,
        nodePos: { x, y, z },
        isValidPos
      });
      
      // ========================================
      // CONSISTENT CAMERA DISTANCE (Every Search)
      // ========================================
      // CRITICAL: Use FIXED distance for consistency across ALL searches
      // No dynamic calculation - always the same zoom level
      // This ensures every search focuses the same way
      const isDocument = node.label === 'Document';
      
      // FIXED distance: Same value every time for same node type
      // Document nodes: 100 units (closer for better detail)
      // Chunk nodes: 150 units (slightly further for context)
      // NO dynamic adjustment - consistency is more important than "smart" calculation
      const distance = isDocument ? 100 : 150;
      
      console.log('[GraphViewer3D] Using FIXED camera distance:', {
        nodeType: isDocument ? 'Document' : 'Chunk',
        distance,
        nodeId: node.id.substring(0, 30) + '...'
      });
      
      // Store active target node for onEngineTick tracking
      activeTargetNodeRef.current = {
        id: node.id,
        label: node.label,
        distance: distance
      };
      
      // CRITICAL: Immediately cache node position so onEngineTick can find it
      // This prevents "node position not found" errors at the start of animation
      nodePositionsRef.current.set(node.id, { x, y, z });
      console.log('[GraphViewer3D] Cached initial node position:', {
        nodeId: node.id,
        nodeLabel: node.label,
        position: { x, y, z }
      });
      
      // Disable controls during animation to prevent conflicts with manual camera control
      try {
        const controls = graphRef.current.controls();
        if (controls) {
          controls.enabled = false;
          controls.enableDamping = false;
        }
      } catch (e) {
        // Ignore errors
      }
      
      // Calculate camera position directly in front of node (negative Z direction)
      // Camera will be at node position, but offset by distance in Z direction
      const targetPos = {
        x: x, // Same X as node
        y: y, // Same Y as node
        z: z + distance, // Directly in front (positive Z offset)
      };
      
      // Get current camera position - use it as starting point (don't reset camera)
      // Only reset if camera is extremely far (prevents "new camera" feeling)
      const currentCameraPos = graphRef.current.cameraPosition();
      
      // Check if camera is extremely far from graph (black screen issue)
      const currentDistance = Math.sqrt(
        currentCameraPos.x * currentCameraPos.x + 
        currentCameraPos.y * currentCameraPos.y + 
        currentCameraPos.z * currentCameraPos.z
      );
      
      // Only reset if camera is extremely far (more lenient threshold)
      const maxSafeDistance = 5000; // Increased from 3000 to prevent unnecessary resets
      let startPos = {
        x: currentCameraPos.x,
        y: currentCameraPos.y,
        z: currentCameraPos.z
      };
      
      // Only reset if camera is extremely far (prevents "new camera" feeling on every query)
      if (currentDistance > maxSafeDistance) {
        console.warn('[GraphViewer3D] Camera extremely far from graph, resetting to safe position:', {
          currentDistance,
          currentPos: startPos,
          nodePos: { x, y, z }
        });
        // Reset to a safe position: slightly above and in front of the node
        startPos = {
          x: x,
          y: y,
          z: z + distance * 2 // Start from a safe distance in front
        };
      }
      
      console.log('[GraphViewer3D] Starting camera animation:', {
        startPos,
        targetPos,
        distance,
        isDocument,
        nodePos: { x, y, z }
      });
      
      const duration = 4000; // Increased from 3000ms to 4000ms for smoother animation (prevents teleportation)
      const startTime = Date.now();
      let lastFrameTime = startTime;
      
      const animate = () => {
        if (!graphRef.current) {
          console.warn('[GraphViewer3D] Graph ref is null during animation');
          setIsAnimating(false);
          setTimeout(() => setAutoRotateEnabled(true), 2000);
          return;
        }
        
        const now = Date.now();
        const elapsed = now - startTime;
        const progress = Math.min(elapsed / duration, 1);
        
        // Use smooth cubic easing for natural camera movement (prevents teleportation)
        // Cubic ease-in-out provides smooth acceleration and deceleration
        const eased = progress < 0.5
          ? 4 * progress * progress * progress
          : 1 - Math.pow(-2 * progress + 2, 3) / 2;
        
        // Track frame time to prevent skipping frames
        const deltaTime = now - lastFrameTime;
        lastFrameTime = now;
        
        const currentPos = {
          x: startPos.x + (targetPos.x - startPos.x) * eased,
          y: startPos.y + (targetPos.y - startPos.y) * eased,
          z: startPos.z + (targetPos.z - startPos.z) * eased,
        };
        
        // Log first few frames to debug
        if (progress < 0.1 || progress > 0.9) {
          console.log('[GraphViewer3D] Animation frame:', {
            progress: progress.toFixed(3),
            eased: eased.toFixed(3),
            currentPos,
            startPos,
            targetPos
          });
        }
        
        try {
          // Try to get controls - this should work based on existing code
          const controls = graphRef.current.controls();
          
          if (controls && controls.object) {
            // Direct Three.js camera and controls manipulation
            // This is the most reliable method
            
            // Calculate distance from origin to prevent camera from going too far
            const distanceFromOrigin = Math.sqrt(
              currentPos.x * currentPos.x + 
              currentPos.y * currentPos.y + 
              currentPos.z * currentPos.z
            );
            
            // Maximum distance to prevent camera from going too far (black screen issue)
            // Reduced from 5000 to 3000 for better safety
            const maxDistance = 3000;
            
            // Also check distance from target node (where graph is)
            const distanceFromNode = Math.sqrt(
              (currentPos.x - x) * (currentPos.x - x) + 
              (currentPos.y - y) * (currentPos.y - y) + 
              (currentPos.z - z) * (currentPos.z - z)
            );
            
            // Clamp if too far from origin OR too far from target node
            if (distanceFromOrigin > maxDistance || distanceFromNode > maxDistance) {
              console.warn('[GraphViewer3D] Camera position too far, clamping:', {
                distanceFromOrigin,
                distanceFromNode,
                currentPos,
                nodePos: { x, y, z }
              });
              
              // Clamp to max distance from node (more important than origin)
              if (distanceFromNode > maxDistance) {
                const scale = maxDistance / distanceFromNode;
                currentPos.x = x + (currentPos.x - x) * scale;
                currentPos.y = y + (currentPos.y - y) * scale;
                currentPos.z = z + (currentPos.z - z) * scale;
              } else {
                // Clamp to max distance from origin
                const scale = maxDistance / distanceFromOrigin;
                currentPos.x *= scale;
                currentPos.y *= scale;
                currentPos.z *= scale;
              }
            }
            
            // Set camera position and target together during animation
            // Both should move smoothly together to prevent jumps
            controls.object.position.set(currentPos.x, currentPos.y, currentPos.z);
            controls.target.set(x, y, z);
            controls.update();
            
            // Log to verify it's working (only first and last frames)
            if (progress < 0.1 || progress > 0.9) {
              console.log('[GraphViewer3D] Using controls API:', {
                cameraPos: controls.object.position.toArray(),
                targetPos: controls.target.toArray(),
                currentPos,
                distanceFromOrigin: Math.sqrt(
                  currentPos.x * currentPos.x + 
                  currentPos.y * currentPos.y + 
                  currentPos.z * currentPos.z
                )
              });
            }
          } else {
            console.warn('[GraphViewer3D] Controls not available, trying cameraPosition method');
            // Fallback to cameraPosition method if controls not available
            try {
              graphRef.current.cameraPosition(currentPos.x, currentPos.y, currentPos.z);
            } catch (e) {
              console.error('[GraphViewer3D] cameraPosition method error:', e);
            }
          }
        } catch (error) {
          console.error('[GraphViewer3D] Error setting camera position:', error);
        }
        
        if (progress < 1) {
          requestAnimationFrame(animate);
        } else {
          // Final frame - ensure camera position and target are exactly at final position
          try {
            const controls = graphRef.current.controls();
            if (controls && controls.object) {
              // Set final camera position and target on last frame
              controls.object.position.set(targetPos.x, targetPos.y, targetPos.z);
              controls.target.set(x, y, z);
              controls.update();
            }
          } catch (e) {
            // Ignore errors
          }
          
          console.log('[GraphViewer3D] Animation complete, reached target');
          
          // ========================================
          // STEP 2: ANIMATION COMPLETION (Smooth Transition to Autorotate)
          // ========================================
          // CRITICAL: Sequence matters for smooth transition
          // 1. Lock target position FIRST (before any state changes)
          // 2. Set controls target immediately
          // 3. Re-enable controls but disable autorotate temporarily
          // 4. Update state flags
          // 5. Enable autorotate after stabilization (2 frames)
          
          // Store node info before clearing
          const nodeInfo = activeTargetNodeRef.current;
          
          // STEP 2.1: Lock target position IMMEDIATELY
          // This must happen FIRST so onEngineTick can use it right away
          lockedTargetPositionRef.current = { x, y, z };
          console.log('[GraphViewer3D] ✓ Locked target position:', {
            position: lockedTargetPositionRef.current,
            nodeId: nodeInfo ? nodeInfo.id.substring(0, 30) + '...' : 'unknown',
            nodeLabel: nodeInfo ? nodeInfo.label : 'unknown'
          });
          
          // STEP 2.2: Clear active tracking refs
          // This prevents onEngineTick from interfering during transition
          activeTargetNodeRef.current = null;
          focusPeriodActiveRef.current = false;
          
          // STEP 2.3: Configure controls for smooth transition
          try {
            const controls = graphRef.current.controls();
            if (controls) {
              // Re-enable controls
              controls.enabled = true;
              controls.enableDamping = true;
              
              // Set target immediately (critical for smooth transition)
              controls.target.set(x, y, z);
              
              // Temporarily disable autorotate (will be enabled after 2 frames)
              // This prevents sudden rotation calculation
              controls.autoRotate = false;
              
              // Force update to apply changes
              controls.update();
              
              console.log('[GraphViewer3D] ✓ Controls configured, autorotate will enable in 2 frames');
            }
          } catch (e) {
            console.error('[GraphViewer3D] Error configuring controls:', e);
          }
          
          // STEP 2.4: Update state flags
          // Set isAnimating to false immediately so onEngineTick can work
          setIsAnimating(false);
          
          // STEP 2.5: Enable autorotate after stabilization (prevents 180° rotation)
          // Use requestAnimationFrame chain to wait 2 frames for controls to stabilize
          requestAnimationFrame(() => {
            requestAnimationFrame(() => {
              try {
                const controls = graphRef.current?.controls();
                if (controls && lockedTargetPositionRef.current) {
                  // Now enable autorotate - controls are stable
                  controls.autoRotate = true;
                  controls.autoRotateSpeed = 0.5;
                  
                  // Ensure target is still locked (safety check)
                  const lockedPos = lockedTargetPositionRef.current;
                  controls.target.set(lockedPos.x, lockedPos.y, lockedPos.z);
                  controls.update();
                  
                  console.log('[GraphViewer3D] ✓ Autorotate enabled after stabilization');
                }
              } catch (e) {
                console.error('[GraphViewer3D] Error enabling autorotate:', e);
              }
              
              // Update state flag
              setAutoRotateEnabled(true);
            });
          });
          
          console.log('[GraphViewer3D] Animation complete, autorotate enabled');
        }
      };
      
      console.log('[GraphViewer3D] Starting animation loop');
      animate();
    };
    
    // Immediately find and fly to target node (no delay)
    try {
      console.log('[GraphViewer3D] Looking for target node with IDs:', highlightedNodeIds);
      
      if (!graphRef.current) {
        console.warn('[GraphViewer3D] Graph ref is null');
        setIsAnimating(false);
        setAutoRotateEnabled(true);
        return;
      }
        console.log('[GraphViewer3D] Graph has', graphData.nodes.length, 'nodes');
        console.log('[GraphViewer3D] First 5 node IDs:', graphData.nodes.slice(0, 5).map(n => `${n.id} (${n.label})`));
      
      // Try to get node position from multiple sources
      let targetNode: GraphNode | null = null;
      let nodeX = 0;
      let nodeY = 0;
      let nodeZ = 0;
      
      // First, prioritize Document nodes (PDF files) - they are more important
      // Find Document nodes first, then fall back to Chunk nodes
      let documentNode: GraphNode | null = null;
      let chunkNode: GraphNode | null = null;
      
      // CRITICAL: Find FIRST Document node from highlightedNodeIds
      // Backend should send Document node IDs first, so we use the first one we find
      console.log('[GraphViewer3D] Searching for nodes in highlightedNodeIds:', {
        totalHighlightedIds: highlightedNodeIds.length,
        highlightedIdsSample: highlightedNodeIds.slice(0, 5).map(id => ({
          id: id.substring(0, 30) + '...',
          fullId: id
        })),
        totalGraphNodes: graphData.nodes.length
      });
      
      for (const nodeId of highlightedNodeIds) {
        const foundNode = graphData.nodes.find((node) => node.id === nodeId) || null;
        if (foundNode) {
          console.log('[GraphViewer3D] Found node for highlighted ID:', {
            highlightedId: nodeId.substring(0, 30) + '...',
            foundNodeId: foundNode.id.substring(0, 30) + '...',
            label: foundNode.label,
            name: foundNode.name,
            position: { x: foundNode.x, y: foundNode.y, z: foundNode.z }
          });
          
          if (foundNode.label === 'Document') {
            // Use FIRST Document node found (most likely the correct one from backend)
            if (!documentNode) {
              documentNode = foundNode;
              console.log('[GraphViewer3D] ✓ Selected Document node (primary target):', {
                id: foundNode.id.substring(0, 50) + '...',
                label: foundNode.label,
                name: foundNode.name,
                position: { x: foundNode.x, y: foundNode.y, z: foundNode.z }
              });
              // Stop after finding first Document node - this is our target
              break;
            }
          } else if (!chunkNode && foundNode.label === 'Chunk') {
            chunkNode = foundNode;
            console.log('[GraphViewer3D] Found Chunk node (backup):', {
              id: foundNode.id.substring(0, 30) + '...',
              label: foundNode.label
            });
          }
        } else {
          console.warn('[GraphViewer3D] Node not found in graphData for highlighted ID:', {
            highlightedId: nodeId.substring(0, 30) + '...',
            totalNodes: graphData.nodes.length,
            sampleNodeIds: graphData.nodes.slice(0, 3).map(n => n.id.substring(0, 30) + '...')
          });
        }
      }
      
      // Prioritize Document node over Chunk node
      targetNode = documentNode || chunkNode;
      
      if (targetNode) {
      // CRITICAL: Try to get position from nodePositionsRef FIRST (most up-to-date, updated every frame)
      // This ensures we get the final stable position, not the initial graphData position
      const cachedPos = nodePositionsRef.current.get(targetNode.id);
      if (cachedPos && (cachedPos.x !== 0 || cachedPos.y !== 0 || cachedPos.z !== 0)) {
        nodeX = cachedPos.x;
        nodeY = cachedPos.y;
        nodeZ = cachedPos.z;
        console.log('[GraphViewer3D] Using cached position (from onEngineTick):', { x: nodeX, y: nodeY, z: nodeZ });
      } else {
        // Fallback to node position from graphData (might be initial position)
        nodeX = targetNode.x ?? 0;
        nodeY = targetNode.y ?? 0;
        nodeZ = targetNode.z ?? 0;
        console.log('[GraphViewer3D] Using graphData position (fallback):', { x: nodeX, y: nodeY, z: nodeZ });
      }
      } else {
        // If not found in graphData, try to get position from cache
        console.log('[GraphViewer3D] Node not found in graphData, trying cache...');
        // Try to get position from cache (updated by onEngineTick)
        for (const nodeId of highlightedNodeIds) {
          const cachedPos = nodePositionsRef.current.get(nodeId);
          if (cachedPos && (cachedPos.x !== 0 || cachedPos.y !== 0 || cachedPos.z !== 0)) {
            // Find node in graphData by ID from cache
            const foundNode = graphData.nodes.find((n) => n.id === nodeId);
            if (foundNode) {
              if (foundNode.label === 'Document' || !targetNode) {
                targetNode = foundNode;
                nodeX = cachedPos.x;
                nodeY = cachedPos.y;
                nodeZ = cachedPos.z;
                console.log('[GraphViewer3D] Using cached position:', { x: nodeX, y: nodeY, z: nodeZ });
                break;
              }
            }
          }
        }
        
        // Fallback: if still not found, use graphData directly
        if (!targetNode && graphData && graphData.nodes) {
            console.log('[GraphViewer3D] Graph has', graphData.nodes.length, 'nodes');
            
            // Prioritize Document nodes
            let documentNodeRef: GraphNode | null = null;
            let chunkNodeRef: GraphNode | null = null;
            
            for (const nodeId of highlightedNodeIds) {
              const foundNode = graphData.nodes.find((node: any) => node.id === nodeId) || null;
              if (foundNode) {
                if (foundNode.label === 'Document') {
                  documentNodeRef = foundNode;
                  console.log('[GraphViewer3D] Found Document node in graph ref:', {
                    id: foundNode.id,
                    label: foundNode.label
                  });
                } else if (!chunkNodeRef) {
                  chunkNodeRef = foundNode;
                  console.log('[GraphViewer3D] Found Chunk node in graph ref (backup):', {
                    id: foundNode.id,
                    label: foundNode.label
                  });
                }
              }
            }
            
            // Prioritize Document node over Chunk node
            targetNode = documentNodeRef || chunkNodeRef;
            
            if (targetNode) {
              const cachedPos = nodePositionsRef.current.get(targetNode.id);
              if (cachedPos) {
                nodeX = cachedPos.x;
                nodeY = cachedPos.y;
                nodeZ = cachedPos.z;
                console.log('[GraphViewer3D] Using cached position from graph ref:', { x: nodeX, y: nodeY, z: nodeZ });
              } else {
                nodeX = targetNode.x ?? 0;
                nodeY = targetNode.y ?? 0;
                nodeZ = targetNode.z ?? 0;
                console.log('[GraphViewer3D] Using graphData position:', { x: nodeX, y: nodeY, z: nodeZ });
              }
            }
          }
        }
      
      if (!targetNode) {
        console.warn('[GraphViewer3D] Target node not found for any of these IDs:', highlightedNodeIds);
        console.log('[GraphViewer3D] Available node IDs in graph:', graphData.nodes.slice(0, 20).map(n => `${n.id.substring(0, 20)}... (${n.label})`));
        console.log('[GraphViewer3D] Available node labels:', [...new Set(graphData.nodes.map(n => n.label))]);
        console.log('[GraphViewer3D] Highlighted node ID samples:', highlightedNodeIds.map(id => id.substring(0, 20) + '...'));
        setIsAnimating(false);
        setAutoRotateEnabled(true);
        return;
      }
      
      // CRITICAL: Store target node ID separately to avoid closure issues
      const targetNodeId = targetNode.id;
      const targetNodeLabel = targetNode.label;
      
      console.log('[GraphViewer3D] Found target node:', {
        id: targetNodeId.substring(0, 50) + '...',
        label: targetNodeLabel,
        position: { x: nodeX, y: nodeY, z: nodeZ },
        isDocument: targetNodeLabel === 'Document'
      });
      
      // ========================================
      // CONSISTENT POSITION RESOLUTION (Every Search)
      // ========================================
      // CRITICAL: Always use the SAME position resolution strategy
      // This ensures consistent behavior across ALL searches
      // Priority: 1) Cache (if valid), 2) Initial position (from above)
      // NO dynamic waiting - use what we have immediately
      
      // Check cache one more time (might have been updated by onEngineTick)
      const finalCachedPos = nodePositionsRef.current.get(targetNodeId);
      
      // Use cached position if valid, otherwise use initial position
      // This ensures we always use the same logic for consistency
      let finalX = nodeX;
      let finalY = nodeY;
      let finalZ = nodeZ;
      
      if (finalCachedPos && (finalCachedPos.x !== 0 || finalCachedPos.y !== 0 || finalCachedPos.z !== 0)) {
        // Use cached position (most up-to-date)
        finalX = finalCachedPos.x;
        finalY = finalCachedPos.y;
        finalZ = finalCachedPos.z;
        console.log('[GraphViewer3D] Using cached position (final check):', {
          nodeId: targetNodeId.substring(0, 30) + '...',
          nodeLabel: targetNodeLabel,
          position: { x: finalX, y: finalY, z: finalZ }
        });
      } else {
        // Use initial position (from graphData or initial cache)
        console.log('[GraphViewer3D] Using initial position:', {
          nodeId: targetNodeId.substring(0, 30) + '...',
          nodeLabel: targetNodeLabel,
          position: { x: finalX, y: finalY, z: finalZ }
        });
      }
      
      // CRITICAL: Always use the same targetNode object
      // Re-find from graphData to ensure we have the latest object
      const currentTargetNode = graphData.nodes.find(n => n.id === targetNodeId);
      const finalTargetNode = currentTargetNode || targetNode;
      
      // Call flyToNode immediately with resolved position
      // No waiting, no dynamic checks - just use what we have
      flyToNode(finalTargetNode, finalX, finalY, finalZ);
    } catch (error) {
      console.error('[GraphViewer3D] Error finding/flying to node:', error);
      setIsAnimating(false);
      setAutoRotateEnabled(true);
    }
    
    return () => {
      // CRITICAL: Cleanup ALL pending operations from this effect
      // This prevents memory leaks and state conflicts across searches
      if (animationTimeoutRef.current) {
        clearTimeout(animationTimeoutRef.current);
        animationTimeoutRef.current = null;
      }
      if (waitForStablePositionRef.current !== null) {
        cancelAnimationFrame(waitForStablePositionRef.current);
        waitForStablePositionRef.current = null;
      }
      
      // CRITICAL: Clear active tracking refs on cleanup
      // This ensures clean state for next search and prevents interference
      // Note: lockedTargetPositionRef is NOT cleared - let it persist for autorotate
      // It will be cleared when new animation starts (in the useEffect body above)
      activeTargetNodeRef.current = null;
      focusPeriodActiveRef.current = false;
      
      // Note: Don't reset isAnimating/autoRotateEnabled in cleanup
      // Let animation complete naturally, state will be updated properly
    };
  }, [highlightedNodeIds, graphData, isLoading]); // Removed isAnimating from dependencies

  // Memoized node rendering function
  const nodeThreeObject = useMemo(() => {
    // Create default material for fallback
    const defaultMaterial = new THREE.SpriteMaterial({
      color: 0xffffff,
      transparent: true,
      opacity: 0.5,
    });
    
    if (!glowTexture) {
      // Return function that always returns a sprite (never null)
      return (node: GraphNode) => {
        const sprite = new THREE.Sprite(defaultMaterial);
        const scale = node.label === 'Document' ? 20 : 4;
        sprite.scale.set(scale, scale, 1);
        return sprite;
      };
    }
    
    // Create sprite materials once and reuse
    const documentMaterial = new THREE.SpriteMaterial({
      map: glowTexture,
      color: 0xff1493, // Deep Pink/Magenta for Document - vibrant and highly visible
      transparent: true,
      opacity: 1.0,
    });
    
    const chunkMaterial = new THREE.SpriteMaterial({
      map: glowTexture,
      color: 0x00aaff, // Cyan for Chunk
      transparent: true,
      opacity: 0.9,
    });
    
    return (node: GraphNode) => {
      const material = node.label === 'Document' ? documentMaterial : chunkMaterial;
      const sprite = new THREE.Sprite(material);
      
      // Document nodes much larger and more visible
      const scale = node.label === 'Document' ? 20 : 4;
      sprite.scale.set(scale, scale, 1);
      
      return sprite;
    };
  }, [glowTexture]);

  // Cleanup texture on unmount
  useEffect(() => {
    return () => {
      if (glowTexture) {
        glowTexture.dispose();
      }
    };
  }, [glowTexture]);

  // Loading state
  if (isLoading) {
    return (
      <div className="w-screen h-screen fixed inset-0 z-0 bg-black flex items-center justify-center">
        <div className="text-center">
          <div className="text-cyan-400 text-xl font-mono mb-4 animate-pulse">
            LOADING NEURAL NETWORK...
          </div>
          <div className="w-16 h-16 border-4 border-cyan-500/30 border-t-cyan-500 rounded-full animate-spin mx-auto" />
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="w-screen h-screen fixed inset-0 z-0 bg-black flex items-center justify-center">
        <div className="text-center text-red-400 font-mono">
          <div className="text-xl mb-2">ERROR</div>
          <div className="text-sm text-white/50">{error}</div>
        </div>
      </div>
    );
  }

  // Empty state
  if (!graphData.nodes || graphData.nodes.length === 0) {
    return (
      <div className="w-screen h-screen fixed inset-0 z-0 bg-black flex items-center justify-center">
        <div className="text-center text-white/50 font-mono">
          <div className="text-xl mb-2">NO DATA</div>
          <div className="text-sm">Graph is empty. Upload documents to begin.</div>
        </div>
      </div>
    );
  }

  return (
    <div className="w-screen h-screen fixed inset-0 z-0 bg-black">
      <ForceGraph3D
        ref={graphRef}
        graphData={graphData}
        nodeThreeObject={nodeThreeObject}
        nodeThreeObjectExtend={true}
        linkDirectionalParticles={1}
        linkDirectionalParticleWidth={0.2}
        linkWidth={0.15}
        linkColor={() => 'rgba(100, 150, 255, 0.2)'}
        backgroundColor="#000000"
        showNavInfo={false}
        enableNavigationControls={true}
        enableNodeDrag={false}
        // @ts-ignore - autoRotate prop exists but types may be outdated
        autoRotate={autoRotateEnabled && !isAnimating}
        autoRotateSpeed={0.5}
        controlType="orbit"
        cameraPosition={{ x: 0, y: 0, z: 250 }}
        cooldownTicks={Infinity}
        warmupTicks={100}
        // @ts-ignore - d3AlphaDecay prop exists but types may be outdated
        d3AlphaDecay={0}
        // @ts-ignore - d3VelocityDecay prop exists but types may be outdated
        d3VelocityDecay={0.9}
        onEngineTick={() => {
          if (!graphRef.current) return;
          
          // CRITICAL: Update node positions cache for camera animation
          // Use graphData state (updated by React) instead of getGraphData() which doesn't exist
          // This allows us to get real-time node positions
          try {
            if (graphData && graphData.nodes) {
              graphData.nodes.forEach((node: any) => {
                if (node.id && (node.x !== undefined || node.y !== undefined || node.z !== undefined)) {
                  nodePositionsRef.current.set(node.id, {
                    x: node.x ?? 0,
                    y: node.y ?? 0,
                    z: node.z ?? 0,
                  });
                }
              });
            }
          } catch (e) {
            // Ignore errors
          }
          
          // CRITICAL: If animating, continuously update camera target to track active target node
          // Only update target, NOT position - position is controlled by animation
          // This prevents conflicts and ensures smooth animation
          if (isAnimating && activeTargetNodeRef.current) {
            try {
              const controls = graphRef.current.controls();
              if (controls && controls.object && controls.enabled === false) {
                // Only track target during animation when controls are disabled
                // This prevents interference with manual camera animation
                let latestPos = nodePositionsRef.current.get(activeTargetNodeRef.current.id) || null;
                
                // If not in cache, try graphData state
                if (!latestPos || (latestPos.x === 0 && latestPos.y === 0 && latestPos.z === 0)) {
                  try {
                    if (graphData && graphData.nodes) {
                      const nodeFromGraph = graphData.nodes.find((n: any) => n.id === activeTargetNodeRef.current!.id);
                      if (nodeFromGraph && (nodeFromGraph.x !== undefined || nodeFromGraph.y !== undefined || nodeFromGraph.z !== undefined)) {
                        latestPos = {
                          x: nodeFromGraph.x ?? 0,
                          y: nodeFromGraph.y ?? 0,
                          z: nodeFromGraph.z ?? 0,
                        };
                        nodePositionsRef.current.set(activeTargetNodeRef.current.id, latestPos);
                      }
                    }
                  } catch (e) {
                    // Ignore errors
                  }
                }
                
                // Update target only if we have valid position
                if (latestPos && (latestPos.x !== 0 || latestPos.y !== 0 || latestPos.z !== 0)) {
                  // Only update target during animation, position is controlled by animate() function
                  controls.target.set(latestPos.x, latestPos.y, latestPos.z);
                }
              }
            } catch (e) {
              // Ignore errors silently during animation
            }
          }
          
          const simulation = graphRef.current.d3Force();
          if (simulation) {
            // CRITICAL: Very high velocityDecay (0.9) to prevent nodes from drifting
            // This keeps nodes almost stationary but still allows subtle movement
            (simulation as any).velocityDecay(1);
            
            // CRITICAL: Keep simulation running continuously - NO DECAY
            // This prevents equilibrium and ensures infinite movement
            simulation.alphaDecay(0);
            simulation.alphaTarget(0.15); // Lower target for very subtle vibration
            
            // Maintain alpha for continuous subtle movement
            const currentAlpha = simulation.alpha();
            if (currentAlpha < 0.15) {
              simulation.alpha(0.2);
            }
            
            // Periodically reset node velocities to prevent drift - VERY AGGRESSIVE
            const tickCount = (graphRef.current as any).__velocityResetTick || 0;
            if (tickCount % 3 === 0) {
              // Every 3 ticks, aggressively reduce node velocities to prevent drift
              const graphState = graphData;
              if (graphState.nodes) {
                graphState.nodes.forEach((node: any) => {
                  // Reduce velocity by 95% to keep nodes in place
                  if (node.vx !== undefined) node.vx *= 0.05;
                  if (node.vy !== undefined) node.vy *= 0.05;
                  if (node.vz !== undefined) node.vz *= 0.05;
                });
              }
            }
            (graphRef.current as any).__velocityResetTick = (tickCount + 1) % 3;
          }
          
          // Configure charge force - balanced for visibility
          const chargeForce = graphRef.current.d3Force('charge');
          if (chargeForce) {
            chargeForce.strength(-800); // Reduced for better node separation
          }
          
          // Configure link distance for proper spacing
          const linkForce = graphRef.current.d3Force('link');
          if (linkForce) {
            linkForce.distance(90); // Increased for better visibility
          }
          
          // CRITICAL: Maximum strength center force to prevent nodes from drifting away
          const centerForce = graphRef.current.d3Force('center');
          if (centerForce) {
            centerForce.strength(2.0); // Maximum center force to keep nodes centered
            centerForce.x(0); // Center X
            centerForce.y(0); // Center Y
            centerForce.z(0); // Center Z
          }
          
          // CRITICAL: Maximum velocityDecay to prevent drift
          if (simulation) {
            (simulation as any).velocityDecay(1); // Very high decay = almost no drift
          }
          
          // ========================================
          // STEP 1: TARGET LOCKING MECHANISM (Every Search)
          // ========================================
          // CRITICAL: Lock target to node position when animation completes
          // This ensures autorotate rotates around the node, not around origin
          // Works for ALL searches: first, second, third, etc.
          try {
            const controls = graphRef.current.controls();
            if (controls && controls.enabled === true) {
              // Check if we have a locked target position (animation completed)
              if (lockedTargetPositionRef.current) {
                const lockedPos = lockedTargetPositionRef.current;
                
                // ALWAYS lock target to node position EVERY FRAME
                // This is the most critical part - prevents drift on every search
                controls.target.set(lockedPos.x, lockedPos.y, lockedPos.z);
                
                // Only enable autorotate if not currently animating
                // This prevents conflicts during animation
                if (!isAnimating) {
                  // Ensure autorotate is enabled (double-check)
                  if (controls.autoRotate !== true) {
                    controls.autoRotate = true;
                    controls.autoRotateSpeed = 0.5;
                  }
                } else {
                  // During animation, disable autorotate
                  controls.autoRotate = false;
                }
                
                // CRITICAL: Force update to ensure target is applied
                controls.update();
              } else if (!isAnimating && autoRotateEnabled) {
                // Fallback: If no locked position but autorotate should be active
                // This handles initial state before first animation
                if (controls.autoRotate !== true) {
                  controls.autoRotate = true;
                  controls.autoRotateSpeed = 0.5;
                }
              }
            }
          } catch (e) {
            // Ignore errors silently - controls might not be ready yet
          }
        }}
        onEngineStop={() => {
          // Restart simulation IMMEDIATELY if it stops - no delay
          // This should never happen with d3AlphaDecay={0}, but safety net
          if (graphRef.current && autoRotateEnabled && !isAnimating) {
            requestAnimationFrame(() => {
              if (graphRef.current && autoRotateEnabled && !isAnimating) {
                try {
                  graphRef.current.d3ReheatSimulation();
                  const simulation = graphRef.current.d3Force();
                  if (simulation) {
                    (simulation as any).velocityDecay(0.5);
                    simulation.alpha(0.25);
                    simulation.alphaDecay(0);
                    simulation.alphaTarget(0.2);
                  }
                } catch (e) {
                  // Ignore errors
                }
              }
            });
          }
        }}
      />
    </div>
  );
}
