"use client";

import React, { useCallback, useMemo } from "react";
import ReactFlow, {
  Node,
  Edge,
  Controls,
  Background,
  useNodesState,
  useEdgesState,
  MiniMap,
  NodeTypes,
} from "reactflow";
import { BookOpen, AlertCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import { KnowledgeNode } from "@/services/aiService";

interface Props {
  nodes: KnowledgeNode[];
  onNodeClick?: (node: KnowledgeNode) => void;
}

// Custom Node Component
const KnowledgeNodeComponent = ({
  data,
  isConnecting,
  selected,
}: {
  data: KnowledgeNode & { onClick?: () => void };
  isConnecting: boolean;
  selected: boolean;
}) => {
  const hasContent = (data.chunk_count ?? 0) > 0;

  return (
    <div
      onClick={data.onClick}
      className={cn(
        "px-4 py-3 rounded-lg border-2 cursor-pointer transition-all shadow-md hover:shadow-lg",
        "bg-white dark:bg-slate-800 backdrop-blur-sm",
        selected
          ? "border-violet-500 shadow-lg shadow-violet-500/20"
          : "border-slate-200 dark:border-slate-700",
        hasContent
          ? "border-green-400 dark:border-green-600"
          : "border-amber-400 dark:border-amber-600",
        isConnecting && "opacity-50"
      )}
      style={{
        minWidth: "180px",
      }}
    >
      <div className="flex items-start gap-2">
        <BookOpen
          className={cn(
            "w-4 h-4 mt-0.5 flex-shrink-0",
            hasContent
              ? "text-green-500 dark:text-green-400"
              : "text-amber-500 dark:text-amber-400"
          )}
        />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-slate-800 dark:text-slate-100 truncate">
            {data.name_vi || data.name}
          </p>
          {data.description && (
            <p className="text-xs text-slate-500 dark:text-slate-400 line-clamp-2 mt-1">
              {data.description}
            </p>
          )}
        </div>
      </div>
      <div className="mt-2 flex items-center justify-between gap-2">
        <span
          className={cn(
            "text-xs px-2 py-1 rounded-full font-medium",
            hasContent
              ? "bg-green-50 dark:bg-green-950/30 text-green-700 dark:text-green-300"
              : "bg-amber-50 dark:bg-amber-950/30 text-amber-700 dark:text-amber-300"
          )}
        >
          {data.chunk_count ?? 0} chunks
        </span>
      </div>
    </div>
  );
};

const nodeTypes: NodeTypes = {
  knowledge: KnowledgeNodeComponent as any,
};

export function KnowledgeGraph({ nodes, onNodeClick }: Props) {
  // Build hierarchical layout
  const { graphNodes, graphEdges } = useMemo(() => {
    const nodeMap = new Map(nodes.map((n) => [n.id, n]));
    const rootNodes = nodes.filter((n) => !n.parent_id);

    // Calculate positions using tree layout algorithm
    const positionMap = new Map<number, { x: number; y: number }>();
    const levelWidth = 250;
    const levelHeight = 150;

    const positionNode = (
      nodeId: number,
      x: number,
      y: number,
      childrenPerLevel: Map<number, KnowledgeNode[]>
    ) => {
      positionMap.set(nodeId, { x, y });

      const children = childrenPerLevel.get(nodeId) || [];
      if (children.length === 0) return;

      const totalWidth = children.length * levelWidth;
      const startX = x - (totalWidth - levelWidth) / 2;

      children.forEach((child, index) => {
        const childX = startX + index * levelWidth;
        const childY = y + levelHeight;
        positionNode(child.id, childX, childY, childrenPerLevel);
      });
    };

    // Group children by parent
    const childrenPerLevel = new Map<number, KnowledgeNode[]>();
    nodes.forEach((node) => {
      if (node.parent_id) {
        if (!childrenPerLevel.has(node.parent_id)) {
          childrenPerLevel.set(node.parent_id, []);
        }
        childrenPerLevel.get(node.parent_id)!.push(node);
      }
    });

    // Position root nodes
    const totalWidth = rootNodes.length * levelWidth;
    const startX = -(totalWidth - levelWidth) / 2;
    rootNodes.forEach((node, index) => {
      positionNode(node.id, startX + index * levelWidth, 0, childrenPerLevel);
    });

    // Create graph nodes
    const graphNodes = nodes.map((node) => {
      const pos = positionMap.get(node.id) || { x: 0, y: 0 };
      return {
        id: node.id.toString(),
        data: {
          ...node,
          onClick: () => onNodeClick?.(node),
        },
        position: pos,
        type: "knowledge",
      } as Node;
    });

    // Create edges
    const graphEdges = nodes
      .filter((n) => n.parent_id != null)
      .map((node) => ({
        id: `${node.parent_id}-${node.id}`,
        source: (node.parent_id as number).toString(),
        target: node.id.toString(),
        animated: false,
        style: {
          stroke: "#cbd5e1",
          strokeWidth: 2,
        },
      })) as Edge[];

    return { graphNodes, graphEdges };
  }, [nodes, onNodeClick]);

  const [flowNodes, setNodes, onNodesChange] = useNodesState(graphNodes);
  const [flowEdges, setEdges, onEdgesChange] = useEdgesState(graphEdges);

  // Update nodes when props change
  React.useEffect(() => {
    setNodes(graphNodes);
  }, [graphNodes, setNodes]);

  React.useEffect(() => {
    setEdges(graphEdges);
  }, [graphEdges, setEdges]);

  if (nodes.length === 0) {
    return (
      <div className="w-full h-screen flex items-center justify-center bg-slate-50 dark:bg-slate-900 rounded-xl">
        <div className="text-center">
          <BookOpen className="w-12 h-12 text-slate-300 dark:text-slate-600 mx-auto mb-3" />
          <p className="text-slate-600 dark:text-slate-400">
            Chưa có Knowledge Node nào
          </p>
          <p className="text-xs text-slate-500 dark:text-slate-500 mt-1">
            Tạo node mới để bắt đầu xây dựng knowledge graph
          </p>
        </div>
      </div>
    );
  }

  const hasEmptyNodes = nodes.some((n) => (n.chunk_count ?? 0) === 0);

  return (
    <div className="w-full h-screen relative rounded-xl overflow-hidden">
      <ReactFlow
        nodes={flowNodes}
        edges={flowEdges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={nodeTypes}
        fitView
      >
        <Background color="#aaa" gap={16} />
        <Controls />
        <MiniMap
          nodeColor={(node) => {
            const data = node.data as KnowledgeNode;
            return (data.chunk_count ?? 0) > 0 ? "#10b981" : "#f59e0b";
          }}
          style={{
            backgroundColor: "#f1f5f9",
            borderRadius: "8px",
          }}
          className="dark:bg-slate-800"
        />
      </ReactFlow>

      {/* Info hint */}
      {hasEmptyNodes && (
        <div className="absolute bottom-4 left-1/2 -translate-x-1/2 flex items-start gap-2 px-4 py-3 bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 rounded-lg text-xs text-amber-700 dark:text-amber-400 shadow-lg max-w-sm">
          <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
          <p>
            Một số nodes <strong>chưa có tài liệu</strong>. Upload PDF/video và liên kết để tạo quiz.
          </p>
        </div>
      )}
    </div>
  );
}
