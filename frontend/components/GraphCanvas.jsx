import React, { useRef, useEffect, useState, useMemo, useCallback } from 'react';

const STATUS_CONFIG = {
  seed: {
    bg: '#ef4444',
    border: '#f87171',
    glow: 'rgba(239, 68, 68, 0.6)',
    label: 'Modified Seed',
    badge: '⚡ SEED',
    textColor: '#ffffff'
  },
  direct_caller: {
    bg: '#f97316',
    border: '#fb923c',
    glow: 'rgba(249, 115, 22, 0.55)',
    label: 'Direct Caller (1-hop)',
    badge: 'CALLER',
    textColor: '#ffffff'
  },
  indirect_caller: {
    bg: '#eab308',
    border: '#facc15',
    glow: 'rgba(234, 179, 8, 0.45)',
    label: 'Indirect Caller (2-hop)',
    badge: 'INDIRECT',
    textColor: '#ffffff'
  },
  test: {
    bg: '#06b6d4',
    border: '#38bdf8',
    glow: 'rgba(6, 182, 212, 0.6)',
    label: 'Unit Test Suite',
    badge: 'TEST',
    textColor: '#ffffff'
  },
  callee: {
    bg: '#8b5cf6',
    border: '#a78bfa',
    glow: 'rgba(139, 92, 246, 0.45)',
    label: 'Dependency / Callee',
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
  E_invoke: { color: 'rgba(249, 115, 22, 0.8)', activeColor: '#fb923c', width: 2, dash: [] },
  E_import: { color: 'rgba(56, 189, 248, 0.65)', activeColor: '#38bdf8', width: 1.5, dash: [4, 4] },
  E_inherit: { color: 'rgba(168, 85, 247, 0.8)', activeColor: '#c084fc', width: 2, dash: [] },
  E_override: { color: 'rgba(236, 72, 153, 0.85)', activeColor: '#f472b6', width: 2, dash: [] },
  E_contain: { color: 'rgba(71, 85, 105, 0.4)', activeColor: '#94a3b8', width: 1.2, dash: [2, 3] },
  default: { color: 'rgba(100, 116, 139, 0.45)', activeColor: '#cbd5e1', width: 1.2, dash: [] }
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
  const [showLabels, setShowLabels] = useState(true);

  const transformRef = useRef(transform);
  transformRef.current = transform;

  const dragStartPos = useRef({ x: 0, y: 0 });
  const positionsRef = useRef(new Map());
  const animFrameRef = useRef(null);
  const alphaRef = useRef(1.0);

  // Compute downstream adjacency for reachability
  const downstreamMap = useMemo(() => {
    const map = new Map();
    nodes.forEach(n => map.set(n.id, new Set()));
    edges.forEach(e => {
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

  // Fit View: Scales and centers graph in viewport
  const fitToBounds = useCallback(() => {
    const container = containerRef.current;
    if (!container || nodes.length === 0) return;
    const posMap = positionsRef.current;
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;

    nodes.forEach(n => {
      const p = posMap.get(n.id);
      if (p && isFinite(p.x) && isFinite(p.y)) {
        if (p.x < minX) minX = p.x;
        if (p.x > maxX) maxX = p.x;
        if (p.y < minY) minY = p.y;
        if (p.y > maxY) maxY = p.y;
      }
    });

    if (!isFinite(minX) || !isFinite(maxX)) return;

    const containerWidth = container.clientWidth || 800;
    const containerHeight = container.clientHeight || 600;

    const padding = 70;
    const graphWidth = Math.max(maxX - minX + padding * 2, 150);
    const graphHeight = Math.max(maxY - minY + padding * 2, 150);
    const centerX = (minX + maxX) / 2;
    const centerY = (minY + maxY) / 2;

    const scaleX = containerWidth / graphWidth;
    const scaleY = containerHeight / graphHeight;
    const targetK = Math.min(Math.max(Math.min(scaleX, scaleY), 0.45), 1.5);

    const targetX = containerWidth / 2 - centerX * targetK;
    const targetY = containerHeight / 2 - centerY * targetK;

    setTransform({ x: targetX, y: targetY, k: targetK });
  }, [nodes]);

  // Synchronously layout & position nodes when `nodes` changes
  useEffect(() => {
    const posMap = positionsRef.current;
    posMap.clear();

    const container = containerRef.current;
    const width = container && container.clientWidth ? container.clientWidth : 800;
    const height = container && container.clientHeight ? container.clientHeight : 600;
    const cx = width / 2;
    const cy = height / 2;

    // 1. Initial Radial Placement
    nodes.forEach((n, idx) => {
      const isSeed = n.status === 'seed';
      const isDirect = n.status && n.status.includes('direct');
      const radius = isSeed ? 50 : isDirect ? 140 : 230;
      const angle = (idx / Math.max(nodes.length, 1)) * 2 * Math.PI;

      posMap.set(n.id, {
        x: cx + radius * Math.cos(angle) + (Math.random() - 0.5) * 20,
        y: cy + radius * Math.sin(angle) + (Math.random() - 0.5) * 20,
        vx: 0,
        vy: 0,
        pinned: false
      });
    });

    // 2. Pre-simulate 80 iterations so it is already settled before first paint
    const ids = Array.from(posMap.keys());
    let simAlpha = 1.0;
    const k_repulse = 2200;
    const k_spring = 0.045;
    const ideal_len = 110;

    for (let it = 0; it < 80; it++) {
      simAlpha *= 0.96;

      // Repulsion
      for (let i = 0; i < ids.length; i++) {
        for (let j = i + 1; j < ids.length; j++) {
          const p1 = posMap.get(ids[i]);
          const p2 = posMap.get(ids[j]);
          const dx = p2.x - p1.x;
          const dy = p2.y - p1.y;
          const dist = Math.hypot(dx, dy) || 1;
          if (dist < 320) {
            const force = Math.min((k_repulse / (dist * dist)), 25) * simAlpha;
            const fx = (dx / dist) * force;
            const fy = (dy / dist) * force;
            p1.vx -= fx; p1.vy -= fy;
            p2.vx += fx; p2.vy += fy;
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
          const force = (dist - ideal_len) * k_spring * simAlpha;
          const fx = (dx / dist) * force;
          const fy = (dy / dist) * force;
          p1.vx += fx; p1.vy += fy;
          p2.vx -= fx; p2.vy -= fy;
        }
      });

      // Centering & velocity update
      ids.forEach(id => {
        const p = posMap.get(id);
        p.vx += (cx - p.x) * 0.02 * simAlpha;
        p.vy += (cy - p.y) * 0.02 * simAlpha;
        p.vx *= 0.65;
        p.vy *= 0.65;
        p.x += Math.max(-12, Math.min(12, p.vx));
        p.y += Math.max(-12, Math.min(12, p.vy));
      });
    }

    alphaRef.current = 0.2; // Start gentle live relaxation

    // Auto-fit immediately to screen
    setTimeout(() => {
      fitToBounds();
    }, 50);
  }, [nodes, edges, fitToBounds]);

  // Resize canvas handler
  const resizeCanvas = useCallback(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;

    const dpr = window.devicePixelRatio || 1;
    const width = container.clientWidth || 800;
    const height = container.clientHeight || 600;

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

  // Drawing Function
  const renderFrame = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;

    ctx.save();
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.scale(dpr, dpr);

    const curTransform = transformRef.current;
    ctx.translate(curTransform.x, curTransform.y);
    ctx.scale(curTransform.k, curTransform.k);

    const posMap = positionsRef.current;
    const activeNodeId = hoveredNode?.id || selectedNodeId;
    const affectedSet = activeNodeId ? getAffectedDownstream(activeNodeId) : null;

    // 1. Draw Subtle Grid Pattern
    ctx.save();
    ctx.strokeStyle = 'rgba(30, 41, 59, 0.45)';
    ctx.lineWidth = 0.5;
    const gridSize = 50;
    const startX = -curTransform.x / curTransform.k - 200;
    const endX = startX + canvas.width / curTransform.k + 400;
    const startY = -curTransform.y / curTransform.k - 200;
    const endY = startY + canvas.height / curTransform.k + 400;

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
      ctx.setLineDash(style.dash || []);

      if (isConnectedToActive) {
        ctx.strokeStyle = '#38bdf8';
        ctx.lineWidth = 2.8;
        ctx.shadowColor = 'rgba(56, 189, 248, 0.85)';
        ctx.shadowBlur = 8;
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

      // Arrowhead pointing towards target
      const angle = Math.atan2(p2.y - p1.y, p2.x - p1.x);
      const arrowLen = isConnectedToActive ? 10 : 7;
      const targetRadius = 24;
      const ax = p2.x - targetRadius * Math.cos(angle);
      const ay = p2.y - targetRadius * Math.sin(angle);

      ctx.setLineDash([]);
      ctx.beginPath();
      ctx.moveTo(ax, ay);
      ctx.lineTo(ax - arrowLen * Math.cos(angle - Math.PI / 6), ay - arrowLen * Math.sin(angle - Math.PI / 6));
      ctx.lineTo(ax - arrowLen * Math.cos(angle + Math.PI / 6), ay - arrowLen * Math.sin(angle + Math.PI / 6));
      ctx.fillStyle = ctx.strokeStyle;
      ctx.fill();

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
      ctx.globalAlpha = isDimmed && !matchesSearch ? 0.22 : 1.0;

      // Glow halo
      if (isActive || isAffected || matchesSearch || isSeed) {
        ctx.beginPath();
        ctx.arc(p.x, p.y, radius + (isActive ? 10 : 6), 0, 2 * Math.PI);
        ctx.fillStyle = isActive ? 'rgba(56, 189, 248, 0.5)' : isAffected ? 'rgba(239, 68, 68, 0.45)' : isSeed ? 'rgba(239, 68, 68, 0.4)' : 'rgba(250, 204, 21, 0.4)';
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

      // Node Icon Letter
      ctx.fillStyle = '#ffffff';
      ctx.font = 'bold 11px Inter, sans-serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      const iconLetter = n.category === 'class' ? 'C' : n.category === 'method' ? 'm' : n.category === 'file' ? 'F' : 'fn';
      ctx.fillText(iconLetter, p.x, p.y);

      // Node Label (rendered when showLabels is true or node is active/hovered)
      if (showLabels || isActive || isAffected || matchesSearch) {
        ctx.textBaseline = 'top';
        ctx.font = isActive ? 'bold 12px Inter, sans-serif' : '11px Inter, sans-serif';
        const displayLabel = n.name.length > 22 ? n.name.substring(0, 20) + '…' : n.name;
        
        // High-contrast dark pill backdrop
        const textMetrics = ctx.measureText(displayLabel);
        const pillWidth = textMetrics.width + 10;
        const pillHeight = 17;
        const pillX = p.x - pillWidth / 2;
        const pillY = p.y + radius + 4;

        ctx.fillStyle = 'rgba(11, 19, 41, 0.9)';
        ctx.fillRect(pillX, pillY, pillWidth, pillHeight);
        ctx.strokeStyle = isActive ? '#38bdf8' : 'rgba(51, 65, 85, 0.7)';
        ctx.lineWidth = 0.8;
        ctx.strokeRect(pillX, pillY, pillWidth, pillHeight);

        ctx.fillStyle = isActive ? '#38bdf8' : isDimmed ? '#94a3b8' : '#f8fafc';
        ctx.fillText(displayLabel, p.x, pillY + 3);

        // Small Badge Above Node
        ctx.font = 'bold 8px Inter, sans-serif';
        ctx.fillStyle = isDimmed ? '#475569' : config.border;
        ctx.fillText(config.badge, p.x, p.y - radius - 11);
      }

      ctx.restore();
    });

    ctx.restore();
  }, [nodes, edges, hoveredNode, selectedNodeId, searchQuery, showLabels, getAffectedDownstream]);

  // Main Animation Loop
  useEffect(() => {
    let isRunning = true;

    const loop = () => {
      if (!isRunning) return;

      const posMap = positionsRef.current;
      const isDraggingNode = !!draggedNodeId;

      // Run live physical relaxation if alpha is active or during drag
      if (alphaRef.current > 0.005 || isDraggingNode) {
        if (!isDraggingNode) alphaRef.current *= 0.97;

        const ids = Array.from(posMap.keys());
        const k_repulse = 1800;
        const k_spring = 0.04;
        const ideal_len = 110;
        const curAlpha = isDraggingNode ? 0.3 : alphaRef.current;

        // Repulsion
        for (let i = 0; i < ids.length; i++) {
          for (let j = i + 1; j < ids.length; j++) {
            const p1 = posMap.get(ids[i]);
            const p2 = posMap.get(ids[j]);
            const dx = p2.x - p1.x;
            const dy = p2.y - p1.y;
            const dist = Math.hypot(dx, dy) || 1;
            if (dist < 300) {
              const force = Math.min((k_repulse / (dist * dist)), 20) * curAlpha;
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
            const force = (dist - ideal_len) * k_spring * curAlpha;
            const fx = (dx / dist) * force;
            const fy = (dy / dist) * force;
            if (!p1.pinned) { p1.vx += fx; p1.vy += fy; }
            if (!p2.pinned) { p2.vx += fx; p2.vy += fy; }
          }
        });

        // Center gravity & velocity damp
        const container = containerRef.current;
        const cx = container ? container.clientWidth / 2 : 400;
        const cy = container ? container.clientHeight / 2 : 300;

        ids.forEach(id => {
          const p = posMap.get(id);
          if (p.pinned) return;
          p.vx += (cx - p.x) * 0.015 * curAlpha;
          p.vy += (cy - p.y) * 0.015 * curAlpha;
          p.vx *= 0.7;
          p.vy *= 0.7;
          p.x += Math.max(-10, Math.min(10, p.vx));
          p.y += Math.max(-10, Math.min(10, p.vy));
        });
      }

      renderFrame();
      animFrameRef.current = requestAnimationFrame(loop);
    };

    animFrameRef.current = requestAnimationFrame(loop);
    return () => {
      isRunning = false;
      cancelAnimationFrame(animFrameRef.current);
    };
  }, [draggedNodeId, edges, renderFrame]);

  // World coordinate projection
  const clientToWorld = (clientX, clientY) => {
    const canvas = canvasRef.current;
    if (!canvas) return { x: 0, y: 0 };
    const rect = canvas.getBoundingClientRect();
    const curTransform = transformRef.current;
    const screenX = clientX - rect.left;
    const screenY = clientY - rect.top;
    const worldX = (screenX - curTransform.x) / curTransform.k;
    const worldY = (screenY - curTransform.y) / curTransform.k;
    return { x: worldX, y: worldY };
  };

  // Hit test
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

  const handleMouseDown = (e) => {
    if (e.button !== 0) return;
    const { x, y } = clientToWorld(e.clientX, e.clientY);
    const clickedNode = getNodeAtPoint(x, y);

    if (clickedNode) {
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
      setIsDraggingCanvas(true);
      dragStartPos.current = { x: e.clientX - transform.x, y: e.clientY - transform.y };
    }
  };

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
        if (p) p.pinned = true;
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
      const newK = Math.max(0.25, Math.min(3.5, t.k * zoomFactor));
      return {
        k: newK,
        x: mouseX - (mouseX - t.x) * (newK / t.k),
        y: mouseY - (mouseY - t.y) * (newK / t.k)
      };
    });
  };

  const reRelaxLayout = () => {
    const posMap = positionsRef.current;
    posMap.forEach(p => {
      p.pinned = false;
      p.vx = (Math.random() - 0.5) * 10;
      p.vy = (Math.random() - 0.5) * 10;
    });
    alphaRef.current = 0.5;
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
        borderRadius: '12px',
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

      {/* Floating Action HUD Controls */}
      <div style={{
        position: 'absolute',
        top: 12,
        right: 12,
        display: 'flex',
        alignItems: 'center',
        gap: 6,
        background: 'rgba(15, 23, 42, 0.92)',
        backdropFilter: 'blur(10px)',
        padding: '5px 8px',
        borderRadius: 8,
        border: '1px solid #334155',
        boxShadow: '0 4px 14px rgba(0, 0, 0, 0.45)',
        zIndex: 10
      }}>
        <button
          onClick={() => setTransform(t => ({ ...t, k: Math.min(t.k * 1.25, 3.5) }))}
          style={{ width: 28, height: 28, background: '#1e293b', color: '#fff', border: '1px solid #334155', borderRadius: 6, cursor: 'pointer', fontWeight: 'bold', fontSize: 14 }}
          title="Zoom In"
        >
          +
        </button>
        <button
          onClick={() => setTransform(t => ({ ...t, k: Math.max(t.k * 0.8, 0.25) }))}
          style={{ width: 28, height: 28, background: '#1e293b', color: '#fff', border: '1px solid #334155', borderRadius: 6, cursor: 'pointer', fontWeight: 'bold', fontSize: 14 }}
          title="Zoom Out"
        >
          −
        </button>
        <button
          onClick={fitToBounds}
          style={{ height: 28, background: '#0284c7', color: '#ffffff', border: 'none', padding: '0 10px', borderRadius: 6, cursor: 'pointer', fontSize: 11, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 4 }}
          title="Auto-Fit and Center Graph"
        >
          <span>🎯</span> Fit View
        </button>
        <button
          onClick={() => setShowLabels(!showLabels)}
          style={{ height: 28, background: showLabels ? '#1e293b' : '#0f172a', color: showLabels ? '#38bdf8' : '#94a3b8', border: '1px solid #334155', padding: '0 8px', borderRadius: 6, cursor: 'pointer', fontSize: 11, fontWeight: 500 }}
          title="Toggle Labels"
        >
          🏷️ {showLabels ? 'Labels: ON' : 'Labels: OFF'}
        </button>
        <button
          onClick={reRelaxLayout}
          style={{ height: 28, background: '#1e293b', color: '#cbd5e1', border: '1px solid #334155', padding: '0 8px', borderRadius: 6, cursor: 'pointer', fontSize: 11, fontWeight: 500 }}
          title="Re-space layout"
        >
          🔄 Rearrange
        </button>
      </div>

      {/* Edge & Node Legend */}
      <div style={{
        position: 'absolute',
        bottom: 12,
        left: 12,
        display: 'flex',
        flexWrap: 'wrap',
        gap: 12,
        background: 'rgba(15, 23, 42, 0.92)',
        backdropFilter: 'blur(8px)',
        padding: '6px 12px',
        borderRadius: 8,
        border: '1px solid #334155',
        fontSize: 11,
        color: '#94a3b8',
        boxShadow: '0 4px 12px rgba(0,0,0,0.3)',
        zIndex: 10
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
          <span style={{ width: 9, height: 9, borderRadius: '50%', background: '#ef4444' }} />
          <span style={{ color: '#fca5a5', fontWeight: 600 }}>Modified Seed</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
          <span style={{ width: 9, height: 9, borderRadius: '50%', background: '#f97316' }} />
          <span style={{ color: '#fdba74', fontWeight: 600 }}>Direct Caller</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
          <span style={{ width: 9, height: 9, borderRadius: '50%', background: '#06b6d4' }} />
          <span style={{ color: '#67e8f9', fontWeight: 600 }}>Test Suite</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
          <span style={{ width: 14, height: 2, background: '#f97316' }} />
          <span>Calls (E_invoke)</span>
        </div>
      </div>
    </div>
  );
}
