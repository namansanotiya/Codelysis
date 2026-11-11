import React, { useRef, useEffect, useState, useMemo, useCallback } from 'react';

const STATUS_CONFIG = {
  seed: {
    bg: '#ef4444',
    border: '#f87171',
    glow: 'rgba(239, 68, 68, 0.55)',
    label: 'Modified Seed',
    badge: '⚡ SEED',
    textColor: '#ffffff'
  },
  direct_caller: {
    bg: '#f97316',
    border: '#fb923c',
    glow: 'rgba(249, 115, 22, 0.5)',
    label: 'Direct Caller (1-hop)',
    badge: 'CALLER (1-HOP)',
    textColor: '#ffffff'
  },
  indirect_caller: {
    bg: '#eab308',
    border: '#facc15',
    glow: 'rgba(234, 179, 8, 0.45)',
    label: 'Indirect Caller (2-hop)',
    badge: 'CALLER (2-HOP)',
    textColor: '#ffffff'
  },
  test: {
    bg: '#06b6d4',
    border: '#38bdf8',
    glow: 'rgba(6, 182, 212, 0.5)',
    label: 'Unit Test Suite',
    badge: 'TEST',
    textColor: '#ffffff'
  },
  callee: {
    bg: '#8b5cf6',
    border: '#a78bfa',
    glow: 'rgba(139, 92, 246, 0.45)',
    label: 'Callee',
    badge: 'CALLEE',
    textColor: '#ffffff'
  },
  normal: {
    bg: '#1e293b',
    border: '#475569',
    glow: 'rgba(71, 85, 105, 0.3)',
    label: 'Normal Entity',
    badge: 'DEF',
    textColor: '#cbd5e1'
  }
};

const EDGE_STYLES = {
  E_invoke: { color: 'rgba(249, 115, 22, 0.75)', activeColor: '#fb923c', width: 2, dash: [] },
  E_import: { color: 'rgba(56, 189, 248, 0.6)', activeColor: '#38bdf8', width: 1.5, dash: [4, 4] },
  E_inherit: { color: 'rgba(168, 85, 247, 0.75)', activeColor: '#c084fc', width: 2.2, dash: [] },
  E_override: { color: 'rgba(236, 72, 153, 0.8)', activeColor: '#f472b6', width: 2.2, dash: [] },
  E_contain: { color: 'rgba(71, 85, 105, 0.35)', activeColor: '#94a3b8', width: 1.2, dash: [2, 3] },
  default: { color: 'rgba(100, 116, 139, 0.4)', activeColor: '#cbd5e1', width: 1.2, dash: [] }
};

export default function GraphCanvas({
  nodes = [],
  edges = [],
  onNodeHover,
  selectedNodeId,
  onSelectNode,
  searchQuery = ''
}) {
  const containerRef = useRef(null);
  const canvasRef = useRef(null);

  const [hoveredNode, setHoveredNode] = useState(null);
  const [transform, setTransform] = useState({ x: 0, y: 0, k: 1 });
  const [isDraggingCanvas, setIsDraggingCanvas] = useState(false);
  const [draggedNodeId, setDraggedNodeId] = useState(null);

  const dragStartPos = useRef({ x: 0, y: 0 });
  const positionsRef = useRef(new Map());
  const animFrameRef = useRef(null);

  // Compute downstream adjacency for reachability
  const downstreamMap = useMemo(() => {
    const map = new Map();
    nodes.forEach(n => map.set(n.id, new Set()));
    edges.forEach(e => {
      // In RepoGraph, if e.edge_type === 'E_invoke', source is caller ref, target is called def
      // So changing target affects source!
      if (map.has(e.target)) map.get(e.target).add(e.source);
      if (map.has(e.source)) map.get(e.source).add(e.target);
    });
    return map;
  }, [nodes, edges]);

  const getAffectedDownstream = useCallback((startId) => {
    const visited = new Set();
    const queue = [startId];
    while (queue.length > 0) {
      const curr = queue.shift();
      const neighbors = downstreamMap.get(curr) || new Set();
      for (const nbr of neighbors) {
        if (!visited.has(nbr) && nbr !== startId) {
          visited.add(nbr);
          queue.push(nbr);
        }
      }
    }
    return visited;
  }, [downstreamMap]);

  // Sync / Initialize Positions on node change
  useEffect(() => {
    const posMap = positionsRef.current;
    const container = containerRef.current;
    const width = container ? container.clientWidth : 800;
    const height = container ? container.clientHeight : 600;

    nodes.forEach((n, idx) => {
      if (!posMap.has(n.id)) {
        const isSeed = n.status === 'seed';
        const isDirect = n.status.includes('direct');
        const radius = isSeed ? 70 : isDirect ? 170 : 270;
        const angle = (idx / Math.max(nodes.length, 1)) * 2 * Math.PI;
        posMap.set(n.id, {
          x: width / 2 + radius * Math.cos(angle) + (Math.random() - 0.5) * 40,
          y: height / 2 + radius * Math.sin(angle) + (Math.random() - 0.5) * 40,
          vx: 0,
          vy: 0,
          pinned: false
        });
      }
    });

    // Clean up removed nodes
    const currentIds = new Set(nodes.map(n => n.id));
    for (const id of posMap.keys()) {
      if (!currentIds.has(id)) posMap.delete(id);
    }
  }, [nodes]);

  // Resize canvas to match container device pixel ratio
  const resizeCanvas = useCallback(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;

    const dpr = window.devicePixelRatio || 1;
    const width = container.clientWidth;
    const height = container.clientHeight;

    if (canvas.width !== width * dpr || canvas.height !== height * dpr) {
      canvas.width = width * dpr;
      canvas.height = height * dpr;
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
    }
  }, []);

  useEffect(() => {
    resizeCanvas();
    window.addEventListener('resize', resizeCanvas);
    return () => window.removeEventListener('resize', resizeCanvas);
  }, [resizeCanvas]);

  // Main Render & Physics Simulation Loop
  useEffect(() => {
    let isRunning = true;
    let iteration = 0;
    const maxIterations = 350;

    const loop = () => {
      if (!isRunning) return;

      const posMap = positionsRef.current;
      const isDraggingNode = !!draggedNodeId;

      // Run physical forces if still relaxing or during node drag
      if (iteration < maxIterations || isDraggingNode) {
        iteration++;
        const k_repulse = 3800;
        const k_spring = 0.045;
        const ideal_len = 110;

        const ids = Array.from(posMap.keys());
        // Repulsion
        for (let i = 0; i < ids.length; i++) {
          for (let j = i + 1; j < ids.length; j++) {
            const p1 = posMap.get(ids[i]);
            const p2 = posMap.get(ids[j]);
            const dx = p2.x - p1.x;
            const dy = p2.y - p1.y;
            const dist = Math.hypot(dx, dy) || 1;
            if (dist < 350) {
              const force = k_repulse / (dist * dist);
              const fx = (dx / dist) * force;
              const fy = (dy / dist) * force;
              if (!p1.pinned) { p1.vx -= fx; p1.vy -= fy; }
              if (!p2.pinned) { p2.vx += fx; p2.vy += fy; }
            }
          }
        }

        // Springs
        edges.forEach(e => {
          const p1 = posMap.get(e.source);
          const p2 = posMap.get(e.target);
          if (p1 && p2) {
            const dx = p2.x - p1.x;
            const dy = p2.y - p1.y;
            const dist = Math.hypot(dx, dy) || 1;
            const force = (dist - ideal_len) * k_spring;
            const fx = (dx / dist) * force;
            const fy = (dy / dist) * force;
            if (!p1.pinned) { p1.vx += fx; p1.vy += fy; }
            if (!p2.pinned) { p2.vx -= fx; p2.vy -= fy; }
          }
        });

        // Center gravity
        const container = containerRef.current;
        const cx = container ? container.clientWidth / 2 : 400;
        const cy = container ? container.clientHeight / 2 : 300;
        ids.forEach(id => {
          const p = posMap.get(id);
          if (p.pinned) return;
          p.vx += (cx - p.x) * 0.003;
          p.vy += (cy - p.y) * 0.003;
          p.vx *= 0.82;
          p.vy *= 0.82;
          p.x += Math.max(-14, Math.min(14, p.vx));
          p.y += Math.max(-14, Math.min(14, p.vy));
        });
      }

      // Draw frame
      drawCanvas();
      animFrameRef.current = requestAnimationFrame(loop);
    };

    animFrameRef.current = requestAnimationFrame(loop);
    return () => {
      isRunning = false;
      cancelAnimationFrame(animFrameRef.current);
    };
  }, [nodes, edges, transform, hoveredNode, selectedNodeId, draggedNodeId, searchQuery]);

  // Canvas Drawing Routine
  const drawCanvas = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;

    ctx.save();
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.scale(dpr, dpr);

    ctx.translate(transform.x, transform.y);
    ctx.scale(transform.k, transform.k);

    const posMap = positionsRef.current;
    const activeNodeId = hoveredNode?.id || selectedNodeId;
    const affectedSet = activeNodeId ? getAffectedDownstream(activeNodeId) : null;

    // 1. Draw Grid Pattern
    ctx.save();
    ctx.strokeStyle = 'rgba(30, 41, 59, 0.4)';
    ctx.lineWidth = 0.5;
    const gridSize = 40;
    const startX = -transform.x / transform.k - 100;
    const endX = startX + canvas.width / transform.k + 200;
    const startY = -transform.y / transform.k - 100;
    const endY = startY + canvas.height / transform.k + 200;

    for (let x = Math.floor(startX / gridSize) * gridSize; x < endX; x += gridSize) {
      ctx.beginPath();
      ctx.moveTo(x, startY);
      ctx.lineTo(x, endY);
      ctx.stroke();
    }
    for (let y = Math.floor(startY / gridSize) * gridSize; y < endY; y += gridSize) {
      ctx.beginPath();
      ctx.moveTo(startX, y);
      ctx.lineTo(endX, y);
      ctx.stroke();
    }
    ctx.restore();

    // 2. Draw Edges
    edges.forEach(e => {
      const p1 = posMap.get(e.source);
      const p2 = posMap.get(e.target);
      if (!p1 || !p2) return;

      const isConnectedToActive = activeNodeId && (
        e.source === activeNodeId || e.target === activeNodeId ||
        (affectedSet?.has(e.source) && affectedSet?.has(e.target))
      );
      const isDimmed = activeNodeId && !isConnectedToActive;

      const style = EDGE_STYLES[e.edge_type] || EDGE_STYLES.default;

      ctx.save();
      ctx.beginPath();
      ctx.setLineDash(style.dash);

      if (isConnectedToActive) {
        ctx.strokeStyle = '#38bdf8';
        ctx.lineWidth = 2.8;
        ctx.shadowColor = 'rgba(56, 189, 248, 0.8)';
        ctx.shadowBlur = 10;
        ctx.globalAlpha = 1.0;
      } else if (isDimmed) {
        ctx.strokeStyle = 'rgba(51, 65, 85, 0.2)';
        ctx.lineWidth = 1;
        ctx.globalAlpha = 0.2;
      } else {
        ctx.strokeStyle = style.color;
        ctx.lineWidth = style.width;
        ctx.globalAlpha = 0.85;
      }

      ctx.moveTo(p1.x, p1.y);
      ctx.lineTo(p2.x, p2.y);
      ctx.stroke();

      // Arrowhead
      const angle = Math.atan2(p2.y - p1.y, p2.x - p1.x);
      const arrowLen = isConnectedToActive ? 10 : 7;
      const targetRadius = 22;
      const ax = p2.x - targetRadius * Math.cos(angle);
      const ay = p2.y - targetRadius * Math.sin(angle);

      ctx.setLineDash([]);
      ctx.beginPath();
      ctx.moveTo(ax, ay);
      ctx.lineTo(ax - arrowLen * Math.cos(angle - Math.PI / 6), ay - arrowLen * Math.sin(angle - Math.PI / 6));
      ctx.lineTo(ax - arrowLen * Math.cos(angle + Math.PI / 6), ay - arrowLen * Math.sin(angle + Math.PI / 6));
      ctx.fillStyle = ctx.strokeStyle;
      ctx.fill();

      // Confidence badge for active edges
      if (isConnectedToActive && e.confidence) {
        const midX = (p1.x + p2.x) / 2;
        const midY = (p1.y + p2.y) / 2;
        ctx.fillStyle = 'rgba(15, 23, 42, 0.9)';
        ctx.fillRect(midX - 16, midY - 8, 32, 14);
        ctx.fillStyle = '#38bdf8';
        ctx.font = 'bold 9px monospace';
        ctx.textAlign = 'center';
        ctx.fillText(`${Math.round(e.confidence * 100)}%`, midX, midY + 3);
      }

      ctx.restore();
    });

    // 3. Draw Nodes
    nodes.forEach(n => {
      const p = posMap.get(n.id);
      if (!p) return;

      const isSeed = n.status === 'seed';
      const isActive = activeNodeId === n.id;
      const isAffected = affectedSet?.has(n.id);
      const isDimmed = activeNodeId && !isActive && !isAffected;
      const matchesSearch = searchQuery && n.name.toLowerCase().includes(searchQuery.toLowerCase());

      const config = STATUS_CONFIG[n.status] || STATUS_CONFIG.normal;
      const baseRadius = isSeed ? 22 : 18;
      const radius = isActive ? baseRadius + 4 : baseRadius;

      ctx.save();
      ctx.globalAlpha = isDimmed && !matchesSearch ? 0.18 : 1.0;

      // Glow Ring
      if (isActive || (isAffected && activeNodeId) || matchesSearch) {
        ctx.beginPath();
        ctx.arc(p.x, p.y, radius + 8, 0, 2 * Math.PI);
        ctx.fillStyle = isActive ? 'rgba(56, 189, 248, 0.45)' : isAffected ? 'rgba(239, 68, 68, 0.4)' : 'rgba(250, 204, 21, 0.4)';
        ctx.fill();
      }

      // Outer Circle
      ctx.beginPath();
      ctx.arc(p.x, p.y, radius, 0, 2 * Math.PI);
      ctx.fillStyle = isActive ? '#0284c7' : isAffected ? '#be123c' : config.bg;
      ctx.fill();
      ctx.lineWidth = isActive || isSeed ? 3 : 2;
      ctx.strokeStyle = isActive ? '#38bdf8' : isAffected ? '#fda4af' : config.border;
      ctx.stroke();

      // Node Icon / Short Kind Initial
      ctx.fillStyle = '#ffffff';
      ctx.font = 'bold 11px Inter, sans-serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      const iconLetter = n.category === 'class' ? 'C' : n.category === 'method' ? 'm' : n.category === 'file' ? 'F' : 'fn';
      ctx.fillText(iconLetter, p.x, p.y);

      // Label below node
      ctx.textBaseline = 'top';
      ctx.font = isActive ? 'bold 12px Inter, sans-serif' : '11px Inter, sans-serif';
      ctx.fillStyle = isDimmed ? '#64748b' : '#f8fafc';
      const displayLabel = n.name.length > 22 ? n.name.substring(0, 20) + '…' : n.name;
      ctx.fillText(displayLabel, p.x, p.y + radius + 6);

      // Small Pill Category Above Node
      ctx.font = '8px Inter, sans-serif';
      ctx.fillStyle = isDimmed ? '#475569' : '#94a3b8';
      ctx.fillText(config.badge, p.x, p.y - radius - 11);

      ctx.restore();
    });

    ctx.restore();
  };

  // Convert client viewport coordinates to World/Graph coordinates
  const clientToWorld = (clientX, clientY) => {
    const canvas = canvasRef.current;
    if (!canvas) return { x: 0, y: 0 };
    const rect = canvas.getBoundingClientRect();
    const screenX = clientX - rect.left;
    const screenY = clientY - rect.top;
    const worldX = (screenX - transform.x) / transform.k;
    const worldY = (screenY - transform.y) / transform.k;
    return { x: worldX, y: worldY };
  };

  // Hit test: Find node under mouse
  const getNodeAtPoint = (worldX, worldY) => {
    const posMap = positionsRef.current;
    for (const n of nodes) {
      const p = posMap.get(n.id);
      if (p) {
        const radius = n.status === 'seed' ? 24 : 20;
        const dist = Math.hypot(p.x - worldX, p.y - worldY);
        if (dist <= radius + 5) {
          return n;
        }
      }
    }
    return null;
  };

  // Drag & Interaction Listeners
  const handleMouseDown = (e) => {
    if (e.button !== 0) return; // Only left click
    const { x, y } = clientToWorld(e.clientX, e.clientY);
    const clickedNode = getNodeAtPoint(x, y);

    if (clickedNode) {
      // Start dragging node
      setDraggedNodeId(clickedNode.id);
      const p = positionsRef.current.get(clickedNode.id);
      if (p) {
        p.pinned = true;
        p.x = x;
        p.y = y;
        p.vx = 0;
        p.vy = 0;
      }
      if (onSelectNode) onSelectNode(clickedNode);
    } else {
      // Start panning canvas
      setIsDraggingCanvas(true);
      dragStartPos.current = { x: e.clientX - transform.x, y: e.clientY - transform.y };
    }
  };

  // Global Mouse Move and Up for rock-solid drag-and-drop
  useEffect(() => {
    const onWindowMouseMove = (e) => {
      if (draggedNodeId) {
        const { x, y } = clientToWorld(e.clientX, e.clientY);
        const p = positionsRef.current.get(draggedNodeId);
        if (p) {
          p.x = x;
          p.y = y;
          p.vx = 0;
          p.vy = 0;
        }
      } else if (isDraggingCanvas) {
        setTransform(t => ({
          ...t,
          x: e.clientX - dragStartPos.current.x,
          y: e.clientY - dragStartPos.current.y
        }));
      } else {
        // Hover detection
        const { x, y } = clientToWorld(e.clientX, e.clientY);
        const found = getNodeAtPoint(x, y);
        if (found !== hoveredNode) {
          setHoveredNode(found);
          if (onNodeHover) {
            if (found) {
              const affectedIds = Array.from(getAffectedDownstream(found.id));
              const affectedNodes = affectedIds.map(id => nodes.find(n => n.id === id)).filter(Boolean);
              onNodeHover(found, affectedNodes);
            } else {
              onNodeHover(null, []);
            }
          }
        }
      }
    };

    const onWindowMouseUp = () => {
      if (draggedNodeId) {
        const p = positionsRef.current.get(draggedNodeId);
        if (p) {
          p.pinned = true; // Keep pinned where user dropped it
        }
        setDraggedNodeId(null);
      }
      setIsDraggingCanvas(false);
    };

    window.addEventListener('mousemove', onWindowMouseMove);
    window.addEventListener('mouseup', onWindowMouseUp);
    return () => {
      window.removeEventListener('mousemove', onWindowMouseMove);
      window.removeEventListener('mouseup', onWindowMouseUp);
    };
  }, [draggedNodeId, isDraggingCanvas, transform, hoveredNode, nodes, getAffectedDownstream, onNodeHover]);

  const handleWheel = (e) => {
    e.preventDefault();
    const zoomFactor = e.deltaY < 0 ? 1.12 : 0.89;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;

    setTransform(t => {
      const newK = Math.max(0.2, Math.min(3.5, t.k * zoomFactor));
      return {
        k: newK,
        x: mouseX - (mouseX - t.x) * (newK / t.k),
        y: mouseY - (mouseY - t.y) * (newK / t.k)
      };
    });
  };

  const resetView = () => {
    const container = containerRef.current;
    if (!container) return;
    setTransform({ x: 0, y: 0, k: 1 });
  };

  return (
    <div
      ref={containerRef}
      style={{
        position: 'relative',
        width: '100%',
        height: '100%',
        overflow: 'hidden',
        background: '#070b14',
        borderRadius: '14px',
        border: '1px solid #1e293b'
      }}
    >
      <canvas
        ref={canvasRef}
        style={{
          display: 'block',
          width: '100%',
          height: '100%',
          cursor: draggedNodeId ? 'grabbing' : isDraggingCanvas ? 'grabbing' : hoveredNode ? 'pointer' : 'grab'
        }}
        onMouseDown={handleMouseDown}
        onWheel={handleWheel}
      />

      {/* Floating Instructions Banner */}
      <div style={{
        position: 'absolute',
        top: 14,
        right: 14,
        background: 'rgba(15, 23, 42, 0.85)',
        backdropFilter: 'blur(8px)',
        border: '1px solid #334155',
        borderRadius: 8,
        padding: '5px 10px',
        fontSize: 11,
        color: '#94a3b8',
        display: 'flex',
        alignItems: 'center',
        gap: 6
      }}>
        <span>💡 <strong>Drag nodes</strong> to rearrange · <strong>Scroll</strong> to zoom · <strong>Hover</strong> to see impact</span>
      </div>

      {/* Zoom / Pan Controls */}
      <div style={{
        position: 'absolute',
        bottom: 16,
        right: 16,
        display: 'flex',
        alignItems: 'center',
        gap: 6,
        background: 'rgba(15, 23, 42, 0.9)',
        backdropFilter: 'blur(10px)',
        padding: '6px 8px',
        borderRadius: 8,
        border: '1px solid #334155'
      }}>
        <button
          onClick={() => setTransform(t => ({ ...t, k: Math.min(t.k * 1.25, 3.5) }))}
          style={{ width: 28, height: 28, background: '#1e293b', color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer', fontWeight: 'bold' }}
          title="Zoom In"
        >
          +
        </button>
        <button
          onClick={() => setTransform(t => ({ ...t, k: Math.max(t.k * 0.8, 0.2) }))}
          style={{ width: 28, height: 28, background: '#1e293b', color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer', fontWeight: 'bold' }}
          title="Zoom Out"
        >
          −
        </button>
        <button
          onClick={resetView}
          style={{ height: 28, background: '#1e293b', color: '#cbd5e1', border: 'none', padding: '0 10px', borderRadius: 6, cursor: 'pointer', fontSize: 11, fontWeight: 500 }}
        >
          Reset
        </button>
      </div>

      {/* Edge Types Legend */}
      <div style={{
        position: 'absolute',
        bottom: 16,
        left: 16,
        display: 'flex',
        gap: 14,
        background: 'rgba(15, 23, 42, 0.85)',
        backdropFilter: 'blur(8px)',
        padding: '6px 12px',
        borderRadius: 8,
        border: '1px solid #334155',
        fontSize: 11,
        color: '#94a3b8'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ width: 14, height: 2, background: '#f97316' }} />
          <span>E_invoke (Call)</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ width: 14, height: 2, background: '#38bdf8' }} />
          <span>E_import</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ width: 14, height: 2, background: '#c084fc' }} />
          <span>E_inherit / E_override</span>
        </div>
      </div>
    </div>
  );
}
