"use client";

/**
 * frontend/src/components/lms/teacher/KnowledgeGraphPanel.tsx
 *
 * Visualize knowledge graph của khóa học dưới dạng node-link diagram.
 * Dùng canvas-based force-directed layout (không cần thư viện nặng).
 * Mỗi node được tô màu theo source_content, cạnh được vẽ theo relation_type.
 */

import React, { useEffect, useRef, useState, useCallback } from "react";
import { lmsApiClient } from "@/services/lmsApiClient";

interface GraphNode {
  id: number;
  name: string;
  name_vi?: string;
  source_content_title?: string;
  auto_generated: boolean;
  chunk_count: number;
  level: number;
  // runtime positions (force-directed)
  x?: number;
  y?: number;
  vx?: number;
  vy?: number;
}

interface GraphEdge {
  source: number;
  target: number;
  relation_type: "prerequisite" | "related" | "extends";
  strength: number;
}

interface KnowledgeGraphPanelProps {
  courseId: number;
  onNodeClick?: (nodeId: number) => void;
}

const EDGE_COLORS = {
  prerequisite: { line: "#F97316", arrow: "#FB923C", text: "#FB923C" }, // orange: "cần học trước"
  extends:      { line: "#3B82F6", arrow: "#60A5FA", text: "#60A5FA" }, // blue: "mở rộng"
  related:      { line: "#94A3B8", arrow: "#CBD5E1", text: "#CBD5E1" }, // gray: "liên quan"
};

const NODE_COLORS = {
  auto:    { light: "#7C3AED", dark: "#A78BFA", glow: "rgba(124, 58, 237, 0.2)" }, // violet
  manual:  { light: "#059669", dark: "#34D399", glow: "rgba(5, 150, 105, 0.2)" }, // emerald
};

export function KnowledgeGraphPanel({ courseId, onNodeClick }: KnowledgeGraphPanelProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [nodes, setNodes] = useState<GraphNode[]>([]);
  const [edges, setEdges] = useState<GraphEdge[]>([]);
  const [loading, setLoading] = useState(true);
  const [hoveredNode, setHoveredNode] = useState<GraphNode | null>(null);
  const animRef = useRef<number | undefined>(undefined);
  const nodesRef = useRef<GraphNode[]>([]);

  // ── Fetch data ───────────────────────────────────────────────────────────────
  const fetchGraph = useCallback(async () => {
    try {
      setLoading(true);
      const res = await lmsApiClient.get<{ data: { nodes: GraphNode[]; edges: GraphEdge[] } }>(
        `/courses/${courseId}/ai/knowledge-graph`
      );
      const { nodes: rawNodes, edges: rawEdges } = res.data.data;

      // Random initial positions
      const w = canvasRef.current?.width ?? 600;
      const h = canvasRef.current?.height ?? 400;
      const positioned = rawNodes.map((n) => ({
        ...n,
        x: 80 + Math.random() * (w - 160),
        y: 80 + Math.random() * (h - 160),
        vx: 0,
        vy: 0,
      }));

      setNodes(positioned);
      nodesRef.current = positioned;
      setEdges(rawEdges);
    } catch (err) {
      console.error("KnowledgeGraph fetch failed", err);
    } finally {
      setLoading(false);
    }
  }, [courseId]);

  useEffect(() => { fetchGraph(); }, [fetchGraph]);

  // ── Force-directed simulation ────────────────────────────────────────────────
  useEffect(() => {
    if (!nodes.length) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const nodeMap = new Map(nodesRef.current.map((n) => [n.id, n]));
    const isDark = window.matchMedia("(prefers-color-scheme: dark)").matches;

    function tick() {
      const ns = nodesRef.current;
      const W = canvas!.width;
      const H = canvas!.height;
      const k = Math.sqrt((W * H) / (ns.length + 1));

      // Repulsion
      for (let i = 0; i < ns.length; i++) {
        ns[i].vx = (ns[i].vx ?? 0) * 0.85;
        ns[i].vy = (ns[i].vy ?? 0) * 0.85;
        for (let j = i + 1; j < ns.length; j++) {
          const dx = (ns[i].x ?? 0) - (ns[j].x ?? 0);
          const dy = (ns[i].y ?? 0) - (ns[j].y ?? 0);
          const dist = Math.sqrt(dx * dx + dy * dy) + 0.01;
          const force = (k * k) / dist;
          ns[i].vx! += (dx / dist) * force * 0.3;
          ns[i].vy! += (dy / dist) * force * 0.3;
          ns[j].vx! -= (dx / dist) * force * 0.3;
          ns[j].vy! -= (dy / dist) * force * 0.3;
        }
      }

      // Attraction along edges
      for (const edge of edges) {
        const a = nodeMap.get(edge.source);
        const b = nodeMap.get(edge.target);
        if (!a || !b) continue;
        const dx = (a.x ?? 0) - (b.x ?? 0);
        const dy = (a.y ?? 0) - (b.y ?? 0);
        const dist = Math.sqrt(dx * dx + dy * dy) + 0.01;
        const target = k * 1.8;
        const force = ((dist - target) / dist) * 0.04 * edge.strength;
        a.vx! -= dx * force;
        a.vy! -= dy * force;
        b.vx! += dx * force;
        b.vy! += dy * force;
      }

      // Center gravity
      for (const n of ns) {
        n.vx! += ((W / 2 - (n.x ?? 0)) / W) * 0.5;
        n.vy! += ((H / 2 - (n.y ?? 0)) / H) * 0.5;
        n.x! += n.vx!;
        n.y! += n.vy!;
        n.x = Math.max(40, Math.min(W - 40, n.x!));
        n.y = Math.max(40, Math.min(H - 40, n.y!));
      }

      // Draw
      ctx!.clearRect(0, 0, W, H);

      // Edges
      for (const edge of edges) {
        const a = nodeMap.get(edge.source);
        const b = nodeMap.get(edge.target);
        if (!a || !b) continue;

        const colors = EDGE_COLORS[edge.relation_type as keyof typeof EDGE_COLORS] || EDGE_COLORS.related;
        const opacity = 0.4 + edge.strength * 0.4;
        const isPrereq = edge.relation_type === "prerequisite";

        ctx!.beginPath();
        ctx!.strokeStyle = colors.line;
        ctx!.globalAlpha = opacity;
        ctx!.lineWidth = isPrereq ? 2.5 : 1.5;

        if (edge.relation_type === "related") {
          ctx!.setLineDash([6, 4]);
        } else {
          ctx!.setLineDash([]);
        }

        ctx!.moveTo(a.x!, a.y!);
        ctx!.lineTo(b.x!, b.y!);
        ctx!.stroke();

        // Draw Arrow for Prerequisite or Extends
        if (isPrereq || edge.relation_type === "extends") {
          const r = 8 + Math.min(b.chunk_count, 20) * 0.6 + 4; // Node radius + padding
          const dx = b.x! - a.x!;
          const dy = b.y! - a.y!;
          const angle = Math.atan2(dy, dx);
          const dist = Math.sqrt(dx * dx + dy * dy);

          // Position arrowhead at the boundary of the target node
          const arrowX = b.x! - r * Math.cos(angle);
          const arrowY = b.y! - r * Math.sin(angle);

          ctx!.save();
          ctx!.translate(arrowX, arrowY);
          ctx!.rotate(angle);
          ctx!.beginPath();
          ctx!.moveTo(0, 0);
          ctx!.lineTo(-8, -5);
          ctx!.lineTo(-8, 5);
          ctx!.closePath();
          ctx!.fillStyle = colors.arrow;
          ctx!.fill();
          ctx!.restore();
        }

        ctx!.setLineDash([]);
        ctx!.globalAlpha = 1;
      }

      // Nodes
      for (const n of ns) {
        const isHovered = n === hoveredNode;
        const r = 8 + Math.min(n.chunk_count, 20) * 0.6;
        const colors = n.auto_generated ? NODE_COLORS.auto : NODE_COLORS.manual;
        const mainColor = isDark ? colors.dark : colors.light;

        // Glow on hover
        if (isHovered) {
          ctx!.beginPath();
          ctx!.arc(n.x!, n.y!, r + 6, 0, Math.PI * 2);
          ctx!.fillStyle = colors.glow;
          ctx!.fill();
        }

        // Gradient build
        const grad = ctx!.createRadialGradient(n.x!, n.y!, r * 0.2, n.x!, n.y!, r);
        grad.addColorStop(0, isDark ? "#fff" : mainColor);
        grad.addColorStop(1, mainColor);

        ctx!.beginPath();
        ctx!.arc(n.x!, n.y!, r, 0, Math.PI * 2);
        ctx!.fillStyle = grad;
        ctx!.fill();

        ctx!.strokeStyle = isDark ? "#fff" : "#312E81";
        ctx!.lineWidth = isHovered ? 3 : 1.5;
        ctx!.stroke();

        // Label
        const label = (n.name_vi || n.name).slice(0, 22);
        ctx!.font = isHovered ? "600 12px Inter, sans-serif" : "500 11px Inter, sans-serif";
        ctx!.textAlign = "center";

        // Label bg for readability
        const textWidth = ctx!.measureText(label).width;
        ctx!.globalAlpha = 0.7;
        ctx!.fillStyle = isDark ? "#0F172A" : "#F8FAFC";
        ctx!.fillRect(n.x! - textWidth/2 - 4, n.y! + r + 6, textWidth + 8, 16);
        ctx!.globalAlpha = 1;

        ctx!.fillStyle = isDark ? "#F8FAFC" : "#1E293B";
        ctx!.fillText(label, n.x!, n.y! + r + 18);
      }

      animRef.current = requestAnimationFrame(tick);
    }

    animRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(animRef.current!);
  }, [nodes, edges, hoveredNode]);

  // ── Mouse hover on canvas ────────────────────────────────────────────────────
  const handleMouseMove = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) return;
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    const scaleX = (canvasRef.current?.width ?? 1) / rect.width;
    const scaleY = (canvasRef.current?.height ?? 1) / rect.height;
    const cx = mx * scaleX;
    const cy = my * scaleY;

    let found: GraphNode | null = null;
    for (const n of nodesRef.current) {
      const r = 8 + Math.min(n.chunk_count, 20) * 0.6;
      const dx = (n.x ?? 0) - cx;
      const dy = (n.y ?? 0) - cy;
      if (Math.sqrt(dx * dx + dy * dy) <= r + 4) {
        found = n;
        break;
      }
    }
    setHoveredNode(found);
  }, []);

  const handleClick = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    if (hoveredNode) onNodeClick?.(hoveredNode.id);
  }, [hoveredNode, onNodeClick]);

  const edgeCounts = { prerequisite: 0, related: 0, extends: 0 };
  edges.forEach((e) => { edgeCounts[e.relation_type as keyof typeof edgeCounts]++; });

  return (
    <div className="space-y-3">
      {/* Stats bar */}
      <div className="flex items-center gap-4 text-[11px] font-medium text-slate-500 dark:text-slate-400">
        <span className="bg-slate-100 dark:bg-slate-800 px-2 py-0.5 rounded-full">{nodes.length} nodes</span>
        <span className="bg-slate-100 dark:bg-slate-800 px-2 py-0.5 rounded-full">{edges.length} edges</span>
        <span className="flex items-center gap-1.5 ml-2">
          <span className="w-2.5 h-2.5 rounded-full bg-violet-600 dark:bg-violet-400 shadow-[0_0_8px_rgba(124,58,237,0.4)]"/> Auto-generated
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-emerald-600 dark:bg-emerald-400 shadow-[0_0_8px_rgba(5,150,105,0.4)]"/> Manual node
        </span>
        <button
          onClick={fetchGraph}
          className="ml-auto text-[11px] font-semibold text-indigo-600 dark:text-indigo-400 hover:text-indigo-700 transition-colors uppercase tracking-wider"
        >
          Refresh Graph
        </button>
      </div>

      {/* Canvas */}
      <div className="relative rounded-xl border border-slate-200 dark:border-slate-800 overflow-hidden bg-slate-50 dark:bg-slate-950">
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center bg-slate-50/80 dark:bg-slate-950/80 z-10">
            <span className="text-sm text-slate-500 animate-pulse">Loading graph...</span>
          </div>
        )}
        <canvas
          ref={canvasRef}
          width={680}
          height={380}
          className="w-full h-auto cursor-crosshair"
          onMouseMove={handleMouseMove}
          onClick={handleClick}
        />
        {/* Hovered node tooltip */}
        {hoveredNode && (
          <div className="absolute bottom-3 left-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg px-3 py-2 text-xs shadow-md max-w-[240px]">
            <div className="font-medium text-slate-900 dark:text-slate-50">{hoveredNode.name_vi || hoveredNode.name}</div>
            {hoveredNode.source_content_title && (
              <div className="text-slate-500 dark:text-slate-400 mt-0.5">từ: {hoveredNode.source_content_title}</div>
            )}
            <div className="text-slate-400 dark:text-slate-500 mt-0.5">{hoveredNode.chunk_count} chunks</div>
          </div>
        )}
      </div>

      {/* Edge legend */}
      <div className="flex items-center gap-6 text-[11px] font-semibold text-slate-400 dark:text-slate-500 uppercase tracking-widest pt-1">
        {Object.entries(EDGE_COLORS).map(([type, colors]) => (
          <span key={type} className="flex items-center gap-2 group transition-colors hover:text-slate-600 dark:hover:text-slate-300">
            <span
              className="w-8 h-0.5 rounded-full relative"
              style={{ background: colors.line }}
            >
              {type !== "related" && (
                <span
                  className="absolute right-0 top-1/2 -translate-y-1/2 w-1.5 h-1.5 rotate-45 border-t-2 border-r-2"
                  style={{ borderColor: colors.line }}
                />
              )}
            </span>
            <span>
              {type} <span className="opacity-50 font-normal">({edgeCounts[type as keyof typeof edgeCounts]})</span>
            </span>
          </span>
        ))}
      </div>
    </div>
  );
}