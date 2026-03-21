"use client";

import { useEffect, useState, useCallback } from "react";
import {
  TrendingDown,
  AlertCircle,
  Brain,
  Lightbulb,
  ArrowRight,
  BookOpen,
} from "lucide-react";
import { cn } from "@/lib/utils";
import analyticsService, { WeaknessOverviewResponse, WeakNode } from "@/services/analyticsService";
import flashcardService from "@/services/flashcardService";
import { FlashcardReviewModal } from "@/components/lms/student/FlashcardReviewModal";
import toast from "react-hot-toast";

interface Props {
  courseId: number;
}

const LEVEL_COLORS = {
  "Rất tốt": "bg-emerald-100 text-emerald-700 dark:bg-emerald-950/30 dark:text-emerald-400 border-emerald-200 dark:border-emerald-800",
  "TB": "bg-amber-100 text-amber-700 dark:bg-amber-950/30 dark:text-amber-400 border-amber-200 dark:border-amber-800",
  "Yếu": "bg-orange-100 text-orange-700 dark:bg-orange-950/30 dark:text-orange-400 border-orange-200 dark:border-orange-800",
  "Cần cải thiện": "bg-red-100 text-red-700 dark:bg-red-950/30 dark:text-red-400 border-red-200 dark:border-red-800",
};

export function WeaknessTracker({ courseId }: Props) {
  const [data, setData] = useState<WeaknessOverviewResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [generatingFor, setGeneratingFor] = useState<number | null>(null);
  const [error, setError] = useState("");

  const [reviewNodeId, setReviewNodeId] = useState<number | null>(null);
  const [reviewNodeName, setReviewNodeName] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await analyticsService.getMyWeaknesses(courseId);
      setData(res.data);
      setError("");
    } catch (e: any) {
      setError(e?.response?.data?.message || "Không thể tải dữ liệu điểm yếu.");
    } finally {
      setLoading(false);
    }
  }, [courseId]);

  useEffect(() => {
    load();
  }, [load]);

  const handleGenerateFlashcards = async (node: WeakNode) => {
    setGeneratingFor(node.node_id);
    try {
      // request AI to generate 3 flashcards specifically targeting the weakness
      await flashcardService.generateFlashcards(courseId, node.node_id, { count: 3 });
      toast.success(`Đã tạo flashcard ôn tập cho "${node.node_name}"!`);
      // Reload stats if needed, but since flashcardStats is usually loaded by FlashcardWidget,
      // a global event or context would be better. For now a toast works.
      setTimeout(() => window.location.reload(), 1500);
    } catch (e: any) {
      toast.error(e?.response?.data?.message || "Tạo flashcard thất bại.");
    } finally {
      setGeneratingFor(null);
    }
  };

  const openReviewModal = (node: WeakNode) => {
    setReviewNodeId(node.node_id);
    setReviewNodeName(node.node_name);
  };

  const closeReviewModal = () => {
    setReviewNodeId(null);
    setReviewNodeName("");
  };

  if (loading) {
    return (
      <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-6 animate-pulse">
        <div className="h-6 w-1/3 bg-slate-200 dark:bg-slate-800 rounded mb-4"></div>
        <div className="space-y-3">
          <div className="h-16 bg-slate-100 dark:bg-slate-800 rounded-xl"></div>
          <div className="h-16 bg-slate-100 dark:bg-slate-800 rounded-xl"></div>
        </div>
      </div>
    );
  }

  if (error || !data) {
    return null; // hide entirely if there's no data / error
  }

  if (data.weak_nodes.length === 0) {
    return (
      <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-8 text-center shadow-sm">
        <div className="w-12 h-12 bg-emerald-100 dark:bg-emerald-950/20 text-emerald-600 rounded-full flex items-center justify-center mx-auto mb-3">
          <TrendingDown className="w-6 h-6" />
        </div>
        <h3 className="text-lg font-bold text-slate-900 dark:text-slate-50">Không có điểm yếu!</h3>
        <p className="text-sm text-slate-500 mt-1">
          Tuyệt vời! Bạn đang làm chủ kiến thức rất tốt.
        </p>
      </div>
    );
  }

  return (
    <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
      {/* Header */}
      <div className="px-5 py-5 border-b border-slate-100 dark:border-slate-800 flex items-start justify-between">
        <div>
          <h3 className="text-lg font-bold text-slate-900 dark:text-slate-50 flex items-center gap-2">
            <AlertCircle className="w-5 h-5 text-orange-500" />
            Điểm yếu của tôi
          </h3>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
            AI phân tích lỗi sai của bạn theo từng chủ đề
          </p>
        </div>
        <div className="text-right">
          <div className="text-2xl font-black text-slate-900 dark:text-slate-50">
            {data.total_wrong_percent}%
          </div>
          <div className="text-xs font-semibold text-slate-500 uppercase tracking-widest">
            Sai sót chung
          </div>
        </div>
      </div>

      {/* Nodes list */}
      <div className="divide-y divide-slate-100 dark:divide-slate-800">
        {data.weak_nodes.map((node) => {
          const colorClass = LEVEL_COLORS[node.mastery_level] || LEVEL_COLORS["TB"];

          return (
            <div key={node.node_id} className="p-5 flex flex-col md:flex-row md:items-center gap-4 hover:bg-slate-50 dark:hover:bg-slate-800/30 transition-colors">
              <div className="flex-1">
                <div className="flex items-center gap-3 mb-1">
                  <h4 className="font-semibold text-slate-900 dark:text-slate-50 text-base">
                    {node.node_name}
                  </h4>
                  <span className={cn("text-xs px-2.5 py-0.5 rounded-full font-semibold border", colorClass)}>
                    {node.status_level}
                  </span>
                </div>
                <div className="flex items-center gap-4 text-xs text-slate-500 dark:text-slate-400">
                  <span className="flex items-center gap-1">
                    <AlertCircle className="w-3.5 h-3.5 text-slate-400" />
                    <strong>{node.wrong_count}</strong> lỗi sai
                  </span>
                  <span className="flex items-center gap-1">
                    <TrendingDown className="w-3.5 h-3.5 text-slate-400" />
                    <strong>{(node.wrong_count / node.total_attempt) * 100}%</strong> tỷ lệ sai
                  </span>
                </div>
              </div>

              {/* Action */}
              <div className="flex-shrink-0 flex items-center gap-2">
                <button
                  onClick={() => openReviewModal(node)}
                  title="Mở modal xem tất cả flashcard của chủ đề này"
                  className="flex items-center justify-center gap-2 px-4 py-2 text-sm font-semibold rounded-xl border bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800/50 active:scale-95 shadow-sm transition-all"
                >
                  <BookOpen className="w-4 h-4" />
                  <span className="hidden sm:inline">Xem lại Flashcard</span>
                </button>
                
                <button
                  onClick={() => handleGenerateFlashcards(node)}
                  disabled={generatingFor === node.node_id}
                  className={cn(
                    "flex items-center justify-center gap-2 px-4 py-2 text-sm font-semibold rounded-xl border transition-all",
                    generatingFor === node.node_id
                      ? "bg-slate-100 border-slate-200 text-slate-400 cursor-not-allowed"
                      : "bg-white dark:bg-slate-800 border-violet-200 dark:border-violet-800 text-violet-600 dark:text-violet-400 hover:bg-violet-50 dark:hover:bg-violet-900/20 active:scale-95 shadow-sm"
                  )}
                >
                  {generatingFor === node.node_id ? (
                    <>
                      <Lightbulb className="w-4 h-4 animate-pulse" />
                      Đang tạo...
                    </>
                  ) : (
                    <>
                      <Brain className="w-4 h-4" />
                      Tạo Flashcard
                    </>
                  )}
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {/* Review Modal */}
      {reviewNodeId !== null && (
        <FlashcardReviewModal
          courseId={courseId}
          nodeId={reviewNodeId}
          nodeName={reviewNodeName}
          isOpen={true}
          onClose={closeReviewModal}
        />
      )}
    </div>
  );
}
