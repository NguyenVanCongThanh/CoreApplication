"use client";

import React, { useEffect, useState, useRef, useCallback } from "react";
import dynamic from "next/dynamic";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { X, ExternalLink, Link2, BookOpen, BrainCircuit } from "lucide-react";
import aiService from "@/services/aiService";

// Phải load dynamic vì Canvas không hỗ trợ SSR
const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), {
  ssr: false,
  loading: () => (
    <div className="flex h-full w-full items-center justify-center bg-slate-50 dark:bg-slate-900 text-slate-500">
      <div className="flex flex-col items-center gap-3 animate-pulse">
        <BrainCircuit size={32} className="text-blue-600" />
        <span className="text-sm font-medium">Đang khởi tạo Engine...</span>
      </div>
    </div>
  ),
});

interface KnowledgeGraphProps {
  courseId: number;
  initialData?: { nodes: any[]; links: any[] };
}

function KnowledgeGraph({ courseId, initialData }: KnowledgeGraphProps) {
  console.log(initialData)
  const [graphData, setGraphData] = useState(initialData || { nodes: [], links: [] });
  const [selectedNode, setSelectedNode] = useState<any | null>(null);
  const [hoveredNode, setHoveredNode] = useState<any | null>(null);
  const [nodeChunks, setNodeChunks] = useState<any[]>([]);
  const [isLoadingChunks, setIsLoadingChunks] = useState(false);

  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<any>(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 });

  // Lấy kích thước lần đầu khi mount - không cần ResizeObserver vì sẽ trigger khi sidebar mở/đóng
  useEffect(() => {
    if (!containerRef.current) return;
    const { width, height } = containerRef.current.getBoundingClientRect();
    setDimensions({ width, height });
  }, []);

  const handleNodeClick = useCallback(async (node: any) => {
    setSelectedNode(node);
    setIsLoadingChunks(true);
    setNodeChunks([]);

    setTimeout(() => {
      if (graphRef.current) {
        // Zoom vào chính giữa node
        graphRef.current.centerAt(node.x, node.y, 800); 
        graphRef.current.zoom(3.5, 800); 
      }
    }, 50); 

    try {
      const chunks = await aiService.getNodeChunks(courseId, node.id);
      setNodeChunks(chunks || []);
    } catch (error) {
      console.error("Lỗi khi fetch chunk verifiable", error);
    } finally {
      setIsLoadingChunks(false);
    }
  }, [courseId]);

  const handleClosePanel = () => {
    setSelectedNode(null);
    if (graphRef.current) {
      graphRef.current.zoomToFit(800, 50); 
    }
  };

  return (
    // Sử dụng màu nền cơ bản của hệ thống theo DESIGN_RYMTH, gỡ bỏ transition-all để chống giật UI Canvas
    <div className="flex h-[80vh] w-full border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden bg-slate-50 dark:bg-slate-950 font-sans shadow-sm relative">
      
      {/* --- KHU VỰC ĐỒ THỊ --- */}
      {/* Gỡ bỏ transition-all, dùng w-full / w-2/3 để snap ngay lập tức */}
      <div 
        ref={containerRef} 
        className={`relative h-full ${selectedNode ? 'w-2/3 border-r border-slate-200 dark:border-slate-800' : 'w-full'}`}
      >
        <div className="absolute top-4 left-4 z-10 pointer-events-none">
          <Badge variant="outline" className="bg-white/80 dark:bg-slate-900/80 border-blue-200 dark:border-blue-900 text-blue-600 dark:text-blue-400">
            <BrainCircuit size={14} className="mr-2" /> AI Knowledge Network
          </Badge>
        </div>

        <ForceGraph2D
          ref={graphRef}
          width={dimensions.width}
          height={dimensions.height}
          graphData={graphData}
          nodeLabel=""
          nodeRelSize={6}
          // Set nền Canvas trong suốt để ăn theo background CSS chuẩn Light/Dark mode
          backgroundColor="rgba(0,0,0,0)" 
          
          // Logic Link an toàn (đã bọc kiểm tra link.source là id hay object)
          linkColor={(link: any) => {
             const isNeighbor = selectedNode && (
               (link.source.id ?? link.source) === selectedNode.id || 
               (link.target.id ?? link.target) === selectedNode.id
             );
             return isNeighbor ? 'rgba(37, 99, 235, 0.6)' : 'rgba(148, 163, 184, 0.3)'; // Primary blue hoặc Slate mờ
          }}
          linkWidth={(link: any) => {
             const isNeighbor = selectedNode && (
               (link.source.id ?? link.source) === selectedNode.id || 
               (link.target.id ?? link.target) === selectedNode.id
             );
             return isNeighbor ? 2 : 1;
          }}
          
          // Hạt chạy truyền dữ liệu
          linkDirectionalParticles={2}
          linkDirectionalParticleWidth={1.5}
          linkDirectionalParticleSpeed={0.006}
          linkDirectionalParticleColor={() => '#3b82f6'} 

          onNodeClick={handleNodeClick}
          onBackgroundClick={handleClosePanel}
          onNodeHover={(node) => setHoveredNode(node)}
          
          // Vẽ Node tĩnh gọn gàng, học thuật
          nodeCanvasObject={(node: any, ctx, globalScale) => {
            const label = node.name || `Node ${node.id}`;
            const fontSize = 12 / globalScale;
            ctx.font = `${fontSize}px Inter, sans-serif`;
            
            const isSelected = selectedNode?.id === node.id;
            const isNeighbor = selectedNode && graphData.links.some((l: any) => 
                ((l.source.id ?? l.source) === selectedNode.id && (l.target.id ?? l.target) === node.id) || 
                ((l.target.id ?? l.target) === selectedNode.id && (l.source.id ?? l.source) === node.id)
            );
            const isHovered = hoveredNode?.id === node.id;

            // Màu Node Academic: Primary (blue-600) hoặc Slate
            ctx.fillStyle = isSelected ? '#f59e0b' : (isHovered ? '#7c3aed' : (isNeighbor ? '#2563eb' : '#64748b'));
            
            ctx.beginPath();
            ctx.arc(node.x, node.y, isSelected ? 6 : (isHovered ? 5.5 : 4), 0, 2 * Math.PI, false);
            ctx.fill();

            // Nhãn tên thông minh: Có viền (stroke) mỏng để dễ đọc trên mọi nền mà không cần hộp nền (box)
            if (isSelected || isNeighbor || isHovered || globalScale > 1.5) {
                ctx.textAlign = 'center';
                ctx.textBaseline = 'top';
                
                // Viền chữ (stroke) giúp đọc được chữ dù đè lên link
                ctx.strokeStyle = 'rgba(255, 255, 255, 0.8)';
                ctx.lineWidth = 2 / globalScale;
                ctx.strokeText(label, node.x, node.y + 6);

                ctx.fillStyle = isSelected ? '#d97706' : '#334155'; // Dark slate text
                ctx.fillText(label, node.x, node.y + 6);
            }
          }}
        />
      </div>

      {/* --- KHU VỰC BẰNG CHỨNG (Verifiability Panel) --- */}
      {selectedNode && (
        <div className="w-1/3 min-w-[320px] bg-white dark:bg-slate-900 flex flex-col z-10">
          
          <div className="flex items-start justify-between p-5 border-b border-slate-100 dark:border-slate-800">
            <div>
              <Badge className="mb-2 bg-blue-50 text-blue-600 border border-blue-200 dark:bg-blue-900/30 dark:border-blue-800 dark:text-blue-400 font-medium">
                VERIFIED CONCEPT
              </Badge>
              <h3 className="text-xl font-bold text-slate-900 dark:text-slate-100 leading-tight">{selectedNode.name}</h3>
            </div>
            <button 
              onClick={handleClosePanel} 
              className="p-1.5 text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition-colors shrink-0"
            >
              <X size={18} />
            </button>
          </div>

          {selectedNode.description && (
             <div className="p-5 bg-slate-50 dark:bg-slate-800/50 border-b border-slate-100 dark:border-slate-800">
               <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Mô tả khái niệm</p>
               <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed">{selectedNode.description}</p>
             </div>
          )}

          <div className="flex-1 overflow-hidden flex flex-col">
            <div className="px-5 pt-5 pb-2">
                <h4 className="font-semibold text-slate-800 dark:text-slate-200 flex items-center gap-2 text-sm">
                  <Link2 size={16} className="text-blue-600"/> Dữ liệu gốc trích xuất
                </h4>
            </div>

            <ScrollArea className="flex-1 px-5 pb-5">
              {isLoadingChunks ? (
                <div className="space-y-3 mt-3">
                  {[1, 2].map((i) => (
                    <Card key={i} className="border-slate-100 dark:border-slate-800 shadow-none animate-pulse">
                      <CardContent className="p-4">
                        <div className="h-3 bg-slate-200 dark:bg-slate-800 rounded w-1/3 mb-3"></div>
                        <div className="h-2 bg-slate-200 dark:bg-slate-800 rounded w-full mb-2"></div>
                        <div className="h-2 bg-slate-200 dark:bg-slate-800 rounded w-5/6"></div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              ) : nodeChunks.length > 0 ? (
                <div className="space-y-3 mt-3">
                  {nodeChunks.map((chunk, idx) => (
                    <Card key={idx} className="border-slate-200 dark:border-slate-700 shadow-none hover:border-blue-300 dark:hover:border-blue-700 transition-colors">
                      <CardContent className="p-4">
                        <div className="flex justify-between items-center mb-3">
                          <span className="flex items-center gap-1 text-xs text-blue-600 dark:text-blue-400 font-medium bg-blue-50 dark:bg-blue-900/20 px-2 py-1 rounded">
                            <BrainCircuit size={12} />
                          </span>
                          <button className="text-slate-400 hover:text-blue-600 transition-colors">
                            <ExternalLink size={14} />
                          </button>
                        </div>
                        <p className="text-sm text-slate-600 dark:text-slate-300 leading-relaxed italic border-l-2 border-slate-300 dark:border-slate-600 pl-3">
                          {chunk.chunk_text}
                        </p>
                        {chunk.source && (
                          <div className="mt-3 flex items-center gap-1.5 text-xs text-slate-400">
                            <BookOpen size={12} />
                            <span>Trích từ: {chunk.source}</span>
                          </div>
                        )}
                      </CardContent>
                    </Card>
                  ))}
                </div>
              ) : (
                <div className="mt-8 flex flex-col items-center justify-center p-6 border border-dashed border-slate-200 dark:border-slate-800 rounded-xl">
                    <BrainCircuit className="text-slate-300 dark:text-slate-600 mb-2" size={24} />
                    <p className="text-slate-500 dark:text-slate-400 text-sm font-medium">Chưa có dữ liệu gốc</p>
                    <p className="text-slate-400 dark:text-slate-500 text-xs mt-1 text-center">Khái niệm này có thể được AI tự động nội suy.</p>
                </div>
              )}
            </ScrollArea>
          </div>
        </div>
      )}
    </div>
  );
}

export default KnowledgeGraph;