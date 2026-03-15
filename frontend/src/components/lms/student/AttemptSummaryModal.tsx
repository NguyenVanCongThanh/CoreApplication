"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import quizService from "@/services/quizService";
import QuizReviewModal from "./QuizReviewModal";
import {
  ArrowLeft,
  Clock,
  CheckCircle,
  XCircle,
  Award,
  Target,
  BarChart3,
  Timer,
  Calendar,
  FileText,
  Eye,
} from "lucide-react";

interface AttemptSummary {
  attempt: {
    id: number;
    quiz_id: number;
    attempt_number: number;
    started_at: string;
    submitted_at: string | null;
    status: string;
    quiz_title: string;
    student_name: string;
  };
  question_breakdown: Array<{
    question_id: number;
    question_text: string;
    question_type: string;
    points: number;
    points_earned: number;
    is_correct: boolean;
    time_spent_seconds: number;
    answered_at: string;
  }>;
  time_breakdown: {
    total_seconds: number;
    total_minutes: number;
    average_per_question: number;
    formatted_duration: string;
  };
  score_breakdown: {
    total_points: number;
    earned_points: number;
    percentage: number;
    passing_score: number;
    is_passed: boolean;
    correct_count: number;
    incorrect_count: number;
    ungraded_count: number;
  };
}

interface AttemptSummaryModalProps {
  attemptId: number;
  onClose: () => void;
  onBack?: () => void;
}

export default function AttemptSummaryModal({
  attemptId,
  onClose,
  onBack,
}: AttemptSummaryModalProps) {
  const [summary, setSummary] = useState<AttemptSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showReview, setShowReview] = useState(false);

  useEffect(() => {
    loadSummary();
  }, [attemptId]);

  const loadSummary = async () => {
    try {
      setLoading(true);
      const response = await quizService.getAttemptSummary(attemptId);
      setSummary(response.data);
    } catch (err: any) {
      console.error("Error loading attempt summary:", err);
      setError(err.response?.data?.error || "Không thể tải thông tin chi tiết");
    } finally {
      setLoading(false);
    }
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleString("vi-VN", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const formatTime = (seconds: number) => {
    if (seconds < 60) return `${seconds}s`;
    const minutes = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${minutes}m ${secs}s`;
  };

  if (loading) {
    return (
      <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
        <div className="bg-white dark:bg-slate-900 rounded-2xl p-12 shadow-2xl border border-slate-200 dark:border-slate-800">
          <div className="w-16 h-16 border-4 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto"></div>
          <p className="text-center mt-4 text-slate-600 dark:text-slate-400 font-medium">Đang tải thông tin...</p>
        </div>
      </div>
    );
  }

  if (error || !summary) {
    return (
      <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
        <div className="bg-white dark:bg-slate-900 rounded-2xl max-w-md w-full p-8 shadow-2xl border border-slate-200 dark:border-slate-800">
          <XCircle className="w-16 h-16 text-red-500 mx-auto mb-4" />
          <h3 className="text-xl font-bold text-center text-slate-900 dark:text-slate-50 mb-2">Có lỗi xảy ra</h3>
          <p className="text-center text-slate-600 dark:text-slate-400 mb-6">{error || "Không thể tải thông tin"}</p>
          <Button onClick={onClose} className="w-full bg-blue-600 hover:bg-blue-700 text-white rounded-xl font-medium">
            Đóng
          </Button>
        </div>
      </div>
    );
  }

  const { attempt, question_breakdown, time_breakdown, score_breakdown } = summary;

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
      <div className="bg-white dark:bg-slate-900 rounded-2xl max-w-6xl w-full max-h-[90vh] overflow-hidden shadow-2xl border border-slate-200 dark:border-slate-800">
        {/* Header */}
        <div className="bg-gradient-to-r from-blue-600 to-blue-700 p-6 text-white">
          <div className="flex items-start justify-between mb-6">
            <div className="flex items-center gap-3">
              {onBack && (
                <button
                  onClick={onBack}
                  className="p-2 hover:bg-white/20 rounded-lg transition-colors"
                >
                  <ArrowLeft className="w-5 h-5" />
                </button>
              )}
              <div>
                <h2 className="text-2xl font-bold mb-1">{attempt.quiz_title}</h2>
                <p className="text-blue-100 text-sm">
                  Lần làm #{attempt.attempt_number} - {formatDate(attempt.started_at)}
                </p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="p-2 hover:bg-white/20 rounded-lg transition-colors"
            >
              ✕
            </button>
          </div>

          {/* Score Summary */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="bg-white/10 backdrop-blur-sm rounded-2xl p-4 border border-white/20">
              <div className="flex items-center gap-2 mb-2">
                <Award className="w-5 h-5 text-blue-100" />
                <span className="text-sm font-medium text-blue-100">Điểm số</span>
              </div>
              <p className="text-3xl font-bold">
                {score_breakdown.earned_points.toFixed(1)}/{score_breakdown.total_points}
              </p>
              <p className="text-sm mt-1 text-blue-100">{score_breakdown.percentage.toFixed(1)}%</p>
            </div>

            <div className="bg-white/10 backdrop-blur-sm rounded-2xl p-4 border border-white/20">
              <div className="flex items-center gap-2 mb-2">
                <Target className="w-5 h-5 text-blue-100" />
                <span className="text-sm font-medium text-blue-100">Kết quả</span>
              </div>
              <p className="text-3xl font-bold">
                {score_breakdown.is_passed ? "Đạt" : "Chưa đạt"}
              </p>
              <p className="text-sm mt-1 text-blue-100">
                Chuẩn: {score_breakdown.passing_score.toFixed(0)}%
              </p>
            </div>

            <div className="bg-white/10 backdrop-blur-sm rounded-2xl p-4 border border-white/20">
              <div className="flex items-center gap-2 mb-2">
                <BarChart3 className="w-5 h-5 text-blue-100" />
                <span className="text-sm font-medium text-blue-100">Đúng/Sai</span>
              </div>
              <p className="text-3xl font-bold">
                {score_breakdown.correct_count}/{question_breakdown.length}
              </p>
              <p className="text-sm mt-1 text-blue-100">
                Sai: {score_breakdown.incorrect_count}
              </p>
            </div>

            <div className="bg-white/10 backdrop-blur-sm rounded-2xl p-4 border border-white/20">
              <div className="flex items-center gap-2 mb-2">
                <Timer className="w-5 h-5 text-blue-100" />
                <span className="text-sm font-medium text-blue-100">Thời gian</span>
              </div>
              <p className="text-2xl font-bold">{time_breakdown.formatted_duration}</p>
              <p className="text-sm mt-1 text-blue-100">
                TB: {formatTime(time_breakdown.average_per_question)}/câu
              </p>
            </div>
          </div>
        </div>

        {/* Content */}
        <div className="p-6 overflow-y-auto max-h-[calc(90vh-280px)]">
          {/* Question Breakdown */}
          <div className="mb-6">
            <h3 className="text-lg font-bold mb-4 flex items-center gap-2">
              <FileText className="w-5 h-5 text-blue-600" />
              Chi tiết từng câu hỏi
            </h3>

            <div className="space-y-3">
              {question_breakdown.map((q, index) => (
                <div
                  key={q.question_id}
                  className={`border-l-4 rounded-2xl p-4 bg-white dark:bg-slate-900 border 
                    ${
                      q.is_correct
                        ? "border-l-green-600 border-r border-b border-slate-200 dark:border-slate-800"
                        : "border-l-red-600 border-r border-b border-slate-200 dark:border-slate-800"
                    }`}
                >
                  <div className="flex items-start gap-4 flex-1">
                    <div
                      className={`w-9 h-9 rounded-lg flex items-center justify-center text-white font-bold text-sm flex-shrink-0 ${
                        q.is_correct ? "bg-green-600 dark:bg-green-600" : "bg-red-600 dark:bg-red-600"
                      }`}
                    >
                      {index + 1}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-2 flex-wrap">
                        {q.is_correct ? (
                          <CheckCircle className="w-5 h-5 text-green-600 dark:text-green-500 flex-shrink-0" />
                        ) : (
                          <XCircle className="w-5 h-5 text-red-600 dark:text-red-500 flex-shrink-0" />
                        )}
                        <span
                          className={`font-semibold text-sm ${
                            q.is_correct
                              ? "text-green-700 dark:text-green-400"
                              : "text-red-700 dark:text-red-400"
                          }`}
                        >
                          {q.is_correct ? "Đúng" : "Sai"}
                        </span>
                        <span className="text-xs bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 px-2 py-1 rounded-lg">
                          {q.question_type}
                        </span>
                      </div>
                      <p className="text-slate-900 dark:text-slate-50 font-medium mb-2 text-sm">{q.question_text}</p>
                      <div className="flex items-center gap-4 text-xs text-slate-600 dark:text-slate-400">
                        <span className="flex items-center gap-1">
                          <Award className="w-3.5 h-3.5" />
                          {q.points_earned.toFixed(1)}/{q.points.toFixed(1)} điểm
                        </span>
                        <span className="flex items-center gap-1">
                          <Clock className="w-3.5 h-3.5" />
                          {formatTime(q.time_spent_seconds)}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Additional Info */}
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6">
            <h4 className="font-bold text-slate-900 dark:text-slate-50 mb-3 flex items-center gap-2 text-sm">
              <Calendar className="w-5 h-5 text-blue-600 dark:text-blue-400" />
              Thông tin bổ sung
            </h4>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
              <div>
                <p className="text-slate-500 dark:text-slate-400 text-xs mb-1">Bắt đầu làm bài</p>
                <p className="font-medium text-slate-900 dark:text-slate-50">{formatDate(attempt.started_at)}</p>
              </div>
              {attempt.submitted_at && (
                <div>
                  <p className="text-slate-500 dark:text-slate-400 text-xs mb-1">Nộp bài</p>
                  <p className="font-medium text-slate-900 dark:text-slate-50">{formatDate(attempt.submitted_at)}</p>
                </div>
              )}
              <div>
                <p className="text-slate-500 dark:text-slate-400 text-xs mb-1">Trạng thái</p>
                <p className="font-medium text-slate-900 dark:text-slate-50">{attempt.status}</p>
              </div>
              <div>
                <p className="text-slate-500 dark:text-slate-400 text-xs mb-1">Tổng thời gian</p>
                <p className="font-medium text-slate-900 dark:text-slate-50">
                  {time_breakdown.total_minutes} phút ({time_breakdown.total_seconds} giây)
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Footer with Review Button */}
        <div className="p-6 bg-white dark:bg-slate-900 border-t border-slate-200 dark:border-slate-800">
          <div className="flex items-center justify-between gap-4 flex-wrap">
            <p className="text-sm text-slate-600 dark:text-slate-400">
              Bạn có thể xem chi tiết đáp án và giải thích cho từng câu hỏi
            </p>
            <button
              onClick={() => setShowReview(true)}
              className="bg-blue-600 hover:bg-blue-700 text-white font-semibold flex items-center gap-2 px-4 py-2 rounded-xl transition-all"
            >
              <Eye className="w-4 h-4" />
              Xem chi tiết
            </button>
          </div>
        </div>
      </div>

      {/* Quiz Review Modal */}
      {showReview && (
        <QuizReviewModal
          attemptId={attemptId}
          onClose={() => setShowReview(false)}
        />
      )}
    </div>
  );
}