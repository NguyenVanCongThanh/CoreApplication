"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, BarChart3, RefreshCw } from "lucide-react";
import lmsService from "@/services/lmsService";
import { progressService, CourseProgress, ProgressDetailItem } from "@/services/progressService";
import { analyticsService, StudentQuizScore } from "@/services/analyticsService";
import { PageLoader, GhostBtn } from "@/components/lms/shared";
import { Course } from "@/types";

import { StatsHeroCards }        from "@/components/lms/student/stats/StatsHeroCards";
import { CourseProgressSection } from "@/components/lms/student/stats/CourseProgressSection";
import { QuizScoreSection }      from "@/components/lms/student/stats/QuizScoreSection";

export default function StudentStatsPage() {
  const { courseId } = useParams<{ courseId: string }>();
  const router = useRouter();
  const id = Number(courseId);

  const [course, setCourse]           = useState<Course | null>(null);
  const [progress, setProgress]       = useState<CourseProgress | null>(null);
  const [progressDetail, setProgressDetail] = useState<ProgressDetailItem[]>([]);
  const [quizScores, setQuizScores]   = useState<StudentQuizScore[]>([]);
  const [loading, setLoading]         = useState(true);
  const [refreshing, setRefreshing]   = useState(false);

  const fetchAll = useCallback(async (showRefresh = false) => {
    if (showRefresh) setRefreshing(true);
    try {
      const [courseRes, prog, detail, scores] = await Promise.all([
        lmsService.getCourse(id),
        progressService.getMyCourseProgress(id),
        progressService.getMyCourseProgressDetail(id),
        analyticsService.getMyQuizScores(id),
      ]);
      setCourse(courseRes?.data ?? null);
      setProgress(prog);
      setProgressDetail(detail);
      setQuizScores(Array.isArray(scores?.data) ? scores.data : (scores as any) ?? []);
    } catch (err) {
      console.error("Failed to load stats:", err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [id]);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const handleMarkComplete = async (contentId: number) => {
    try {
      await progressService.markContentComplete(contentId);
      await fetchAll(true);
    } catch (err) {
      console.error("Failed to mark complete:", err);
    }
  };

  if (loading) return <PageLoader message="Đang tải thống kê..." />;

  // ─── Derived stats ────────────────────────────────────────────────────────
  const passedQuizzes    = quizScores.filter(q => q.is_passed).length;
  const totalQuizzes     = quizScores.length;
  const avgPct           = totalQuizzes > 0
    ? quizScores.reduce((sum, q) => sum + (q.best_percentage ?? 0), 0) / totalQuizzes
    : null;

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950">
      {/* ── Header ── */}
      <header className="sticky top-0 z-30 bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 shadow-sm">
        <div className="max-w-5xl mx-auto px-4 h-14 flex items-center gap-3">
          <GhostBtn
            size="sm"
            icon={<ArrowLeft className="w-4 h-4" />}
            onClick={() => router.back()}
          >
            <span className="hidden sm:inline">Quay lại</span>
          </GhostBtn>
          <span className="text-slate-300 dark:text-slate-700">/</span>
          <BarChart3 className="w-4 h-4 text-blue-600 dark:text-blue-400 flex-shrink-0" />
          <h1 className="flex-1 text-base font-bold text-slate-900 dark:text-slate-50 truncate">
            Thống kê của tôi
            {course && (
              <span className="font-normal text-slate-500 dark:text-slate-400 ml-1">
                — {course.title}
              </span>
            )}
          </h1>
          <button
            onClick={() => fetchAll(true)}
            disabled={refreshing}
            className="p-2 rounded-lg text-slate-500 hover:text-slate-700 dark:hover:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 transition-all disabled:opacity-40"
            title="Làm mới"
          >
            <RefreshCw className={`w-4 h-4 ${refreshing ? "animate-spin" : ""}`} />
          </button>
        </div>
      </header>

      {/* ── Body ── */}
      <main className="max-w-5xl mx-auto px-4 py-8 space-y-8">

        {/* KPI cards */}
        <StatsHeroCards
          progress={progress}
          passedQuizzes={passedQuizzes}
          totalQuizzes={totalQuizzes}
          avgPct={avgPct}
        />

        {/* Progress section */}
        <CourseProgressSection
          progress={progress}
          items={progressDetail}
          onMarkComplete={handleMarkComplete}
          loading={refreshing}
        />

        {/* Quiz scores */}
        <QuizScoreSection scores={quizScores} courseId={id} />

      </main>
    </div>
  );
}