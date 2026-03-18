"use client";

/**
 * AIDiagnosisModal.tsx
 * Shows AI-powered error diagnosis for a wrong quiz answer.
 * Includes deep link back to the source document/video.
 *
 * Usage:
 *   <AIDiagnosisModal
 *     attemptId={123}
 *     questionId={456}
 *     questionText="..."
 *     onClose={() => ...}
 *   />
 */

import { useState, useEffect } from "react";
import {
  X, Sparkles, BookOpen, Video, AlertCircle,
  ChevronRight, Brain, Lightbulb, Target
} from "lucide-react";
import aiService, { DiagnosisResult } from "@/services/aiService";
import { cn } from "@/lib/utils";

interface Props {
  attemptId: number;
  questionId: number;
  questionText: string;
  wrongAnswer: string;
  courseId: number;
  onClose: () => void;
}

const GAP_COLORS: Record<string, { bg: string; text: string; icon: React.ReactNode }> = {
  misconception:         { bg: "bg-slate-50 dark:bg-slate-800",    text: "text-slate-700 dark:text-slate-300",   icon: <AlertCircle className="w-4 h-4" /> },
  missing_prerequisite:  { bg: "bg-slate-50 dark:bg-slate-800",    text: "text-slate-700 dark:text-slate-300",   icon: <BookOpen className="w-4 h-4" /> },
  careless_error:        { bg: "bg-slate-50 dark:bg-slate-800",    text: "text-slate-700 dark:text-slate-300",   icon: <Target className="w-4 h-4" /> },
  unknown:               { bg: "bg-slate-50 dark:bg-slate-800",    text: "text-slate-700 dark:text-slate-300",   icon: <Brain className="w-4 h-4" /> },
};

const GAP_LABEL: Record<string, string> = {
  misconception: "Hiểu sai khái niệm",
  missing_prerequisite: "Thiếu kiến thức nền",
  careless_error: "Lỗi bất cẩn",
  unknown: "Chưa xác định",
};

const BLOOM_LABEL: Record<string, string> = {
  remember: "Nhớ",
  understand: "Hiểu",
  apply: "Áp dụng",
  analyze: "Phân tích",
  evaluate: "Đánh giá",
  create: "Sáng tạo",
};

export default function AIDiagnosisModal({
  attemptId,
  questionId,
  questionText,
  wrongAnswer,
  courseId,
  onClose,
}: Props) {
  const [loading, setLoading] = useState(true);
  const [result, setResult] = useState<DiagnosisResult | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    aiService
      .diagnoseWrongAnswer(attemptId, questionId, wrongAnswer, courseId)
      .then(setResult)
      .catch((e) => setError(e?.response?.data?.error ?? "Không thể phân tích lỗi này."))
      .finally(() => setLoading(false));
  }, [attemptId, questionId, wrongAnswer, courseId]);

  const gapCfg = result
    ? (GAP_COLORS[result.gap_type] ?? GAP_COLORS.unknown)
    : GAP_COLORS.unknown;

  const deepLinkHref = (() => {
    const dl = result?.deep_link;
    if (!dl) return null;
    const base = `/lms/student/courses`;
    return dl.url_fragment ?? null;
  })();

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
      <div className="bg-white dark:bg-slate-900 rounded-2xl max-w-xl w-full shadow-lg border border-slate-200 dark:border-slate-800 overflow-hidden">

        {/* Header */}
        <div className="flex items-center gap-3 px-6 py-4 bg-blue-600 text-white border-b border-blue-700 dark:border-blue-900">
          <div className="w-8 h-8 rounded-lg bg-white/20 flex items-center justify-center flex-shrink-0">
            <Sparkles className="w-4 h-4" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="font-bold text-sm">AI Phân tích lỗi</p>
            <p className="text-xs text-white/70 truncate">{questionText}</p>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-white/20 transition-all">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Body */}
        <div className="p-6">
          {loading && (
            <div className="flex flex-col items-center py-10 gap-4">
              <div className="w-12 h-12 rounded-full border-4 border-slate-200 dark:border-slate-700 border-t-blue-600 dark:border-t-blue-400 animate-spin" />
              <p className="text-sm text-slate-600 dark:text-slate-400 text-center">
                AI đang phân tích bài làm của bạn…
              </p>
            </div>
          )}

          {error && (
            <div className="flex items-start gap-3 p-4 rounded-2xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900">
              <AlertCircle className="w-5 h-5 text-slate-600 dark:text-slate-400 flex-shrink-0 mt-0.5" />
              <p className="text-sm text-slate-800 dark:text-slate-300">{error}</p>
            </div>
          )}

          {result && !loading && (
            <div className="space-y-5">

              {/* Gap type badge */}
              <div className={cn("flex items-center gap-3 px-4 py-3 rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900", gapCfg.bg)}>
                <span className={cn("text-slate-600 dark:text-slate-400", gapCfg.text)}>{gapCfg.icon}</span>
                <div className="flex-1">
                  <p className={cn("text-xs font-semibold uppercase tracking-wider text-slate-600 dark:text-slate-400")}>
                    Loại lỗi: {GAP_LABEL[result.gap_type] ?? result.gap_type}
                  </p>
                  <p className={cn("text-sm font-medium mt-1 text-slate-800 dark:text-slate-200")}>
                    {result.knowledge_gap}
                  </p>
                </div>
                <span className="text-xs text-slate-500 dark:text-slate-500 flex-shrink-0">
                  {(result.confidence * 100).toFixed(0)}% tin cậy
                </span>
              </div>

              {/* Explanation */}
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <Brain className="w-4 h-4 text-blue-600 dark:text-blue-400" />
                  <p className="text-xs font-semibold uppercase tracking-wider text-slate-600 dark:text-slate-400">
                    Phân tích
                  </p>
                </div>
                <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900 p-4">
                  <p className="text-sm text-slate-800 dark:text-slate-200 leading-relaxed">
                    {result.explanation}
                  </p>
                </div>
              </div>

              {/* Study suggestion */}
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <Lightbulb className="w-4 h-4 text-blue-600 dark:text-blue-400" />
                  <p className="text-xs font-semibold uppercase tracking-wider text-slate-600 dark:text-slate-400">
                    Gợi ý ôn tập
                  </p>
                </div>
                <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900 p-4">
                  <p className="text-sm text-slate-800 dark:text-slate-200 leading-relaxed">
                    {result.study_suggestion}
                  </p>
                </div>
              </div>

              {/* Deep link to source */}
              {result.deep_link && (
                <div className="flex items-start gap-3 p-4 rounded-2xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900">
                  {result.deep_link.source_type === "video"
                    ? <Video className="w-5 h-5 text-blue-600 dark:text-blue-400 flex-shrink-0 mt-0.5" />
                    : <BookOpen className="w-5 h-5 text-blue-600 dark:text-blue-400 flex-shrink-0 mt-0.5" />
                  }
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-semibold text-slate-600 dark:text-slate-400 uppercase tracking-wider mb-1">
                      Nguồn tài liệu
                    </p>
                    {result.deep_link.source_type === "document" && result.deep_link.page_number && (
                      <p className="text-sm text-slate-800 dark:text-slate-200 font-medium">
                        Trang {result.deep_link.page_number} của tài liệu
                      </p>
                    )}
                    {result.deep_link.source_type === "video" && result.deep_link.start_time_sec !== undefined && (
                      <p className="text-sm text-slate-800 dark:text-slate-200 font-medium">
                        Video tại {Math.floor(result.deep_link.start_time_sec / 60)}:
                        {String(result.deep_link.start_time_sec % 60).padStart(2, "0")}
                      </p>
                    )}
                    {deepLinkHref && (
                      <p className="text-xs text-slate-600 dark:text-slate-400 mt-1 font-mono">
                        {deepLinkHref}
                      </p>
                    )}
                  </div>
                  <ChevronRight className="w-4 h-4 text-slate-400 dark:text-slate-600 flex-shrink-0" />
                </div>
              )}

            </div>
          )}
        </div>

        {/* Footer */}
        {result && !loading && (
          <div className="px-6 pb-5 border-t border-slate-200 dark:border-slate-800">
            <button
              onClick={onClose}
              className="w-full mt-5 py-2.5 bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold rounded-xl transition-all active:scale-95"
            >
              Đã hiểu, đóng lại
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
