"use client";

/**
 * Student Course Detail Page
 * Route: /lms/student/courses/[courseId]
 *
 * Layout:
 *  ┌──────────── Header (title + tab switcher) ─────────────┐
 *  ├── Sidebar (sections / progress) ─┬── Main content ─────┤
 *  │   Section list with ✓ marks      │  [Học tập] ContentViewer + nav
 *  │                                  │  [Thống kê] KPI + progress + quiz
 *  └───────────────────────────────────┴────────────────────┘
 */

import { useEffect, useState, useCallback, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft, ChevronDown, ChevronRight, Menu, X,
  Play, FileText, Image as ImageIcon, HelpCircle,
  MessageSquare, Megaphone, File as FileIcon, BookOpen,
  BarChart3, CheckCircle2, AlertCircle, Lock
} from "lucide-react";

import lmsService      from "@/services/lmsService";
import progressService, { CourseProgress, ProgressDetailItem } from "@/services/progressService";
import analyticsService, { StudentQuizScore }                  from "@/services/analyticsService";

import ContentViewer from "@/components/lms/student/ContentViewer";
import { Badge, ContentTypeBadge, PageLoader, GhostBtn, ProgressBar } from "@/components/lms/shared";
import { Content, Course, Section } from "@/types";
import { cn } from "@/lib/utils";

// ─── Content type icon map ────────────────────────────────────────────────────

const CONTENT_ICON: Record<string, React.ReactNode> = {
  VIDEO:        <Play          className="w-3.5 h-3.5" />,
  DOCUMENT:     <FileText      className="w-3.5 h-3.5" />,
  IMAGE:        <ImageIcon     className="w-3.5 h-3.5" />,
  TEXT:         <FileText      className="w-3.5 h-3.5" />,
  QUIZ:         <HelpCircle    className="w-3.5 h-3.5" />,
  FORUM:        <MessageSquare className="w-3.5 h-3.5" />,
  ANNOUNCEMENT: <Megaphone     className="w-3.5 h-3.5" />,
};

// ─── Tab type ─────────────────────────────────────────────────────────────────

type RightTab = "learn" | "stats";

// ─────────────────────────────────────────────────────────────────────────────
// SIDEBAR
// ─────────────────────────────────────────────────────────────────────────────

interface SidebarSectionProps {
  section: Section;
  index: number;
  contents: Content[];
  loading: boolean;
  isExpanded: boolean;
  onToggle: () => void;
  activeContentId: number | null;
  onSelect: (c: Content) => void;
  completedIds: Set<number>;
}

function SidebarSection({
  section, index, contents, loading,
  isExpanded, onToggle, activeContentId, onSelect,
  completedIds,
}: SidebarSectionProps) {
  const mandatoryCount    = contents.filter(c => c.is_mandatory).length;
  const completedMandatory = contents.filter(c => c.is_mandatory && completedIds.has(c.id)).length;

  return (
    <div className="border-b border-slate-100 dark:border-slate-800 last:border-b-0">
      {/* Section header */}
      <button
        className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors"
        onClick={onToggle}
      >
        <div className="w-6 h-6 rounded-full bg-blue-50 dark:bg-blue-950/20 text-blue-600 dark:text-blue-400 flex items-center justify-center text-xs font-bold flex-shrink-0 border border-blue-200 dark:border-blue-800">
          {index + 1}
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-slate-800 dark:text-slate-200 truncate">{section.title}</p>
          {contents.length > 0 && (
            <p className="text-xs text-slate-500 mt-0.5">
              {mandatoryCount > 0
                ? `${completedMandatory}/${mandatoryCount} bắt buộc`
                : `${contents.length} nội dung`}
            </p>
          )}
        </div>
        {isExpanded
          ? <ChevronDown  className="w-4 h-4 text-slate-400 flex-shrink-0" />
          : <ChevronRight className="w-4 h-4 text-slate-400 flex-shrink-0" />}
      </button>

      {/* Content items */}
      {isExpanded && (
        <div className="pb-1">
          {loading && !contents.length ? (
            <div className="px-4 py-3 space-y-2">
              {[0, 1, 2].map(i => (
                <div key={i} className="h-8 bg-slate-100 dark:bg-slate-800 rounded-lg animate-pulse" />
              ))}
            </div>
          ) : contents.length === 0 ? (
            <p className="px-4 py-3 text-xs text-slate-400">Chưa có nội dung</p>
          ) : (
            contents.map((c, i) => {
              const isActive = c.id === activeContentId;
              const isDone   = completedIds.has(c.id);
              return (
                <button
                  key={c.id}
                  className={cn(
                    "w-full flex items-center gap-2.5 px-4 py-2.5 text-left transition-colors",
                    isActive
                      ? "bg-blue-50 dark:bg-blue-900/20 border-r-2 border-blue-600"
                      : "hover:bg-slate-50 dark:hover:bg-slate-800/50"
                  )}
                  onClick={() => onSelect(c)}
                >
                  {/* Content type icon */}
                  <span className={cn(
                    "flex-shrink-0",
                    isActive ? "text-blue-600 dark:text-blue-400" : "text-slate-400 dark:text-slate-500"
                  )}>
                    {CONTENT_ICON[c.type] ?? <FileIcon className="w-3.5 h-3.5" />}
                  </span>

                  {/* Title */}
                  <span className={cn(
                    "text-sm flex-1 truncate",
                    isActive
                      ? "font-semibold text-blue-700 dark:text-blue-300"
                      : "text-slate-700 dark:text-slate-300"
                  )}>
                    {i + 1}. {c.title}
                  </span>

                  {/* Status dot */}
                  <span className="flex-shrink-0 w-4 flex items-center justify-center">
                    {isDone ? (
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
                    ) : c.is_mandatory ? (
                      <span className="w-1.5 h-1.5 rounded-full bg-orange-400" title="Bắt buộc" />
                    ) : null}
                  </span>
                </button>
              );
            })
          )}
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// STATS TAB CONTENT
// ─────────────────────────────────────────────────────────────────────────────

// ── KPI cards ──

function KpiCard({
  label, value, sub, accent, pct,
}: {
  label: string; value: string; sub?: string; accent: string; pct?: number;
}) {
  return (
    <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-4 shadow-sm">
      <p className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wide mb-1">{label}</p>
      <p className="text-2xl font-extrabold text-slate-900 dark:text-slate-50 leading-tight">{value}</p>
      {sub && <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">{sub}</p>}
      {pct !== undefined && (
        <div className="mt-2 h-1.5 w-full bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
          <div className={cn("h-full rounded-full transition-all duration-700", accent)} style={{ width: `${Math.min(pct, 100)}%` }} />
        </div>
      )}
    </div>
  );
}

// ── Progress list ──

interface ProgressListProps {
  items: ProgressDetailItem[];
  onMarkComplete: (id: number) => Promise<void>;
}

function ProgressList({ items, onMarkComplete }: ProgressListProps) {
  const mandatory = items.filter(i => i.is_mandatory);
  const pending   = mandatory.filter(i => !i.is_completed);
  const done      = mandatory.filter(i => i.is_completed);

  const displayed = [...pending, ...done].slice(0, 8);

  if (items.length === 0) {
    return <p className="text-sm text-slate-400 dark:text-slate-500 text-center py-8">Không có dữ liệu tiến độ.</p>;
  }

  return (
    <div className="space-y-2">
      {displayed.map(item => (
        <ProgressItemRow key={item.content_id} item={item} onMarkComplete={onMarkComplete} />
      ))}
      {mandatory.length > 8 && (
        <p className="text-xs text-center text-slate-400 dark:text-slate-500">
          +{mandatory.length - 8} nội dung khác
        </p>
      )}
    </div>
  );
}

function ProgressItemRow({
  item, onMarkComplete,
}: {
  item: ProgressDetailItem;
  onMarkComplete: (id: number) => Promise<void>;
}) {
  const [marking, setMarking] = useState(false);

  const handleMark = async () => {
    setMarking(true);
    try { await onMarkComplete(item.content_id); } finally { setMarking(false); }
  };

  return (
    <div className={cn(
      "flex items-center gap-3 px-4 py-3 rounded-xl transition-all",
      item.is_completed
        ? "bg-emerald-50 dark:bg-emerald-950/20 border border-emerald-200 dark:border-emerald-800/50"
        : "bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800"
    )}>
      <div className="flex-shrink-0">
        {item.is_completed
          ? <CheckCircle2 className="w-4 h-4 text-emerald-500" />
          : item.is_mandatory
            ? <Lock className="w-4 h-4 text-orange-400" />
            : <div className="w-4 h-4 rounded-full border-2 border-slate-300 dark:border-slate-600" />}
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-slate-800 dark:text-slate-200 truncate">{item.content_title}</p>
        <p className="text-xs text-slate-500 dark:text-slate-400">{item.section_title}</p>
      </div>
      {item.is_mandatory && !item.is_completed && (
        <button
          onClick={handleMark}
          disabled={marking}
          className={cn(
            "flex-shrink-0 text-xs font-semibold px-3 py-1.5 rounded-lg transition-all active:scale-95",
            marking
              ? "bg-slate-100 dark:bg-slate-800 text-slate-400 cursor-not-allowed"
              : "bg-orange-500 hover:bg-orange-600 text-white"
          )}
        >
          {marking ? "Đang lưu..." : "Đánh dấu xong"}
        </button>
      )}
    </div>
  );
}

// ── Quiz scores list ──

const STATUS_CFG = {
  not_started: { label: "Chưa làm",  cls: "bg-slate-100 dark:bg-slate-800 text-slate-500" },
  in_progress: { label: "Đang làm",  cls: "bg-amber-50 dark:bg-amber-950/30 text-amber-600 dark:text-amber-400" },
  submitted:   { label: "Đã nộp",    cls: "bg-blue-50 dark:bg-blue-950/30 text-blue-600 dark:text-blue-400" },
  passed:      { label: "Đã đạt",    cls: "bg-emerald-50 dark:bg-emerald-950/30 text-emerald-600 dark:text-emerald-400" },
  failed:      { label: "Chưa đạt",  cls: "bg-red-50 dark:bg-red-950/30 text-red-500 dark:text-red-400" },
};

function QuizScoreCard({ score }: { score: StudentQuizScore }) {
  const router = useRouter();
  const cfg    = STATUS_CFG[score.status] ?? STATUS_CFG.not_started;
  const pct    = score.best_percentage ?? 0;
  const barColor =
    score.status === "passed"  ? "bg-emerald-500" :
    score.status === "failed"  ? "bg-red-400"     :
    score.status === "not_started" ? "bg-slate-200 dark:bg-slate-700" : "bg-blue-400";

  return (
    <div
      className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-4 shadow-sm hover:border-slate-300 dark:hover:border-slate-700 transition-all cursor-pointer group"
      onClick={() => router.push(`/lms/student/quiz/${score.quiz_id}/history`)}
    >
      <div className="flex items-start justify-between gap-3 mb-3">
        <p className="text-sm font-semibold text-slate-900 dark:text-slate-50 truncate flex-1">{score.quiz_title}</p>
        <span className={cn("flex-shrink-0 text-xs font-semibold px-2 py-0.5 rounded-full", cfg.cls)}>
          {cfg.label}
        </span>
      </div>
      {score.status !== "not_started" && (
        <>
          <div className="flex items-center gap-2 mb-1">
            <div className="flex-1 h-1.5 bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
              <div className={cn("h-full rounded-full transition-all duration-700", barColor)} style={{ width: `${Math.min(pct, 100)}%` }} />
            </div>
            <span className="text-xs font-bold text-slate-600 dark:text-slate-300 w-10 text-right flex-shrink-0">
              {pct.toFixed(0)}%
            </span>
          </div>
          <p className="text-xs text-slate-400 dark:text-slate-500">
            {score.attempts_count} lần làm
            {score.passing_score != null && ` · Chuẩn: ${score.passing_score}%`}
          </p>
        </>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// MAIN PAGE
// ─────────────────────────────────────────────────────────────────────────────

export default function StudentCourseDetailPage() {
  const { courseId } = useParams<{ courseId: string }>();
  const router       = useRouter();
  const id           = Number(courseId);

  // ── Core state ──
  const [course,          setCourse]          = useState<Course | null>(null);
  const [sections,        setSections]        = useState<Section[]>([]);
  const [sectionContents, setSectionContents] = useState<Record<number, Content[]>>({});
  const [loadingSection,  setLoadingSection]  = useState<Record<number, boolean>>({});
  const [expanded,        setExpanded]        = useState<Set<number>>(new Set());
  const [activeContent,   setActiveContent]   = useState<Content | null>(null);
  const [loadingPage,     setLoadingPage]     = useState(true);
  const [sidebarOpen,     setSidebarOpen]     = useState(false);
  const [rightTab,        setRightTab]        = useState<RightTab>("learn");

  // ── Progress state ──
  const [progress,        setProgress]        = useState<CourseProgress | null>(null);
  const [completedIds,    setCompletedIds]    = useState<Set<number>>(new Set());
  const [progressDetail,  setProgressDetail]  = useState<ProgressDetailItem[]>([]);
  const [markingComplete, setMarkingComplete] = useState(false);

  // ── Stats state ──
  const [quizScores,    setQuizScores]    = useState<StudentQuizScore[]>([]);
  const [statsLoading,  setStatsLoading]  = useState(false);
  const [statsLoaded,   setStatsLoaded]   = useState(false);

  // Timer ref for auto-complete
  const autoCompleteTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // ─── Load progress ────────────────────────────────────────────────────────

  const loadProgress = useCallback(async () => {
    try {
      const [prog, detail] = await Promise.all([
        progressService.getMyCourseProgress(id),
        progressService.getMyCourseProgressDetail(id),
      ]);
      if (prog) {
        setProgress(prog);
        setCompletedIds(new Set(prog.completed_content_ids ?? []));
      }
      setProgressDetail(detail ?? []);
    } catch {
      // Progress API may not be available yet — degrade gracefully
    }
  }, [id]);

  // ─── Load stats (lazy: only when switching to stats tab) ─────────────────

  const loadStats = useCallback(async () => {
    if (statsLoaded) return;
    setStatsLoading(true);
    try {
      const res = await analyticsService.getMyQuizScores(id);
      setQuizScores(Array.isArray(res?.data) ? res.data : (res as any) ?? []);
      setStatsLoaded(true);
    } catch {
      // fail silently
    } finally {
      setStatsLoading(false);
    }
  }, [id, statsLoaded]);

  // ─── Load course + sections ───────────────────────────────────────────────

  useEffect(() => {
    (async () => {
      try {
        const [courseRes, sectionsRes] = await Promise.all([
          lmsService.getCourse(id),
          lmsService.listSections(id),
        ]);
        setCourse(courseRes?.data ?? null);
        const secs: Section[] = sectionsRes?.data ?? [];
        setSections(secs);

        if (secs.length > 0) {
          const first = secs[0];
          setExpanded(new Set([first.id]));
          loadSectionContents(first.id, true);
        }
      } catch {
        router.back();
      } finally {
        setLoadingPage(false);
      }
    })();
    loadProgress();
  }, [id]); // eslint-disable-line

  // ─── Load section contents ────────────────────────────────────────────────

  const loadSectionContents = useCallback(async (sectionId: number, autoSelect = false) => {
    if (sectionContents[sectionId]) {
      if (autoSelect && !activeContent) {
        const first = sectionContents[sectionId][0];
        if (first) setActiveContent(first);
      }
      return;
    }
    setLoadingSection(prev => ({ ...prev, [sectionId]: true }));
    try {
      const res   = await lmsService.listContent(sectionId);
      const items: Content[] = res?.data ?? [];
      setSectionContents(prev => ({ ...prev, [sectionId]: items }));
      if (autoSelect && !activeContent && items.length > 0) {
        setActiveContent(items[0]);
      }
    } finally {
      setLoadingSection(prev => ({ ...prev, [sectionId]: false }));
    }
  }, [sectionContents, activeContent]);

  const toggleSection = useCallback((sectionId: number) => {
    setExpanded(prev => {
      const next = new Set(prev);
      if (next.has(sectionId)) {
        next.delete(sectionId);
      } else {
        next.add(sectionId);
        loadSectionContents(sectionId);
      }
      return next;
    });
  }, [loadSectionContents]);

  // ─── Mark content complete ────────────────────────────────────────────────

  const handleMarkComplete = useCallback(async (contentId: number) => {
    if (completedIds.has(contentId) || markingComplete) return;
    setMarkingComplete(true);
    try {
      const res = await progressService.markContentComplete(contentId);
      console.log(res)
      setCompletedIds(prev => new Set([...prev, contentId]));
      await loadProgress(); // refresh summary
    } catch {
      // fail silently; will retry on next interaction
    } finally {
      setMarkingComplete(false);
    }
  }, [completedIds, markingComplete, loadProgress]);

  // ─── Select content ───────────────────────────────────────────────────────

  const handleSelectContent = useCallback((c: Content) => {
    setActiveContent(c);
    setSidebarOpen(false);

    // Clear any pending timer
    if (autoCompleteTimer.current) clearTimeout(autoCompleteTimer.current);

    // Auto-complete non-quiz mandatory content after 3 s of viewing
    if (c.is_mandatory && !completedIds.has(c.id) && c.type !== "QUIZ") {
      autoCompleteTimer.current = setTimeout(() => {
        handleMarkComplete(c.id);
      }, 3000);
    }
  }, [completedIds, handleMarkComplete]);

  // Cleanup timer on unmount
  useEffect(() => () => {
    if (autoCompleteTimer.current) clearTimeout(autoCompleteTimer.current);
  }, []);

  // Switch to stats tab: load quiz scores lazily
  const handleTabSwitch = useCallback((tab: RightTab) => {
    setRightTab(tab);
    if (tab === "stats") loadStats();
  }, [loadStats]);

  // ─── Derived progress numbers ─────────────────────────────────────────────

  const totalMandatory = progress?.total_mandatory
    ?? Object.values(sectionContents).flat().filter(c => c.is_mandatory).length;
  const completedCount = progress?.completed_count ?? completedIds.size;
  const progressPct    = totalMandatory > 0 ? Math.round((completedCount / totalMandatory) * 100) : 0;

  const passedQuizzes = quizScores.filter(q => q.is_passed).length;
  const avgPct        = quizScores.length > 0
    ? quizScores.reduce((s, q) => s + (q.best_percentage ?? 0), 0) / quizScores.length
    : null;

  if (loadingPage) return <PageLoader message="Đang tải khóa học..." />;

  // ─── Sidebar JSX ──────────────────────────────────────────────────────────

  const SidebarContent = (
    <div className="h-full flex flex-col">
      {/* Progress header */}
      <div className="px-4 pt-5 pb-4 border-b border-slate-200 dark:border-slate-800">
        <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-2">
          Tiến độ học tập
        </p>
        <ProgressBar
          value={completedCount}
          max={totalMandatory || 1}
          color="blue"
          showPercent={false}
          className="mb-1"
        />
        <p className="text-xs text-slate-500 dark:text-slate-400">
          {completedCount}/{totalMandatory} bài bắt buộc
          {totalMandatory > 0 && ` · ${progressPct}%`}
        </p>
      </div>

      {/* Section list */}
      <div className="flex-1 overflow-y-auto">
        {sections.length === 0 ? (
          <div className="px-4 py-8 text-center">
            <BookOpen className="w-8 h-8 text-slate-300 dark:text-slate-700 mx-auto mb-2" />
            <p className="text-sm text-slate-400">Khóa học chưa có nội dung</p>
          </div>
        ) : (
          sections.map((sec, i) => (
            <SidebarSection
              key={sec.id}
              section={sec}
              index={i}
              contents={sectionContents[sec.id] ?? []}
              loading={!!loadingSection[sec.id]}
              isExpanded={expanded.has(sec.id)}
              onToggle={() => toggleSection(sec.id)}
              activeContentId={activeContent?.id ?? null}
              onSelect={handleSelectContent}
              completedIds={completedIds}
            />
          ))
        )}
      </div>
    </div>
  );

  // ─────────────────────────────────────────────────────────────────────────
  // RENDER
  // ─────────────────────────────────────────────────────────────────────────

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 flex flex-col">

      {/* ── Header ── */}
      <header className="sticky top-0 z-30 bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 shadow-sm">
        <div className="max-w-screen-2xl mx-auto px-4 h-14 flex items-center gap-3">
          <GhostBtn
            size="sm"
            icon={<ArrowLeft className="w-4 h-4" />}
            onClick={() => router.push("/lms/student")}
          >
            <span className="hidden sm:inline">Quay lại</span>
          </GhostBtn>

          <span className="text-slate-300 dark:text-slate-700 select-none">/</span>

          <div className="flex-1 min-w-0">
            <h1 className="text-base font-bold text-slate-900 dark:text-slate-50 truncate">
              {course?.title ?? "Khóa học"}
            </h1>
          </div>

          {/* Tab switcher pill */}
          <div className="hidden sm:flex items-center gap-1 bg-slate-100 dark:bg-slate-800 rounded-xl p-1 flex-shrink-0">
            {(["learn", "stats"] as RightTab[]).map(tab => (
              <button
                key={tab}
                onClick={() => handleTabSwitch(tab)}
                className={cn(
                  "flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg transition-colors",
                  rightTab === tab
                    ? "bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-50 shadow-sm"
                    : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100"
                )}
              >
                {tab === "stats" && <BarChart3 className="w-3.5 h-3.5" />}
                {tab === "learn" ? "Học tập" : "Thống kê"}
              </button>
            ))}
          </div>

          {/* Mobile: sidebar toggle */}
          <button
            className="lg:hidden p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-600 dark:text-slate-400"
            onClick={() => setSidebarOpen(true)}
          >
            <Menu className="w-5 h-5" />
          </button>
        </div>
      </header>

      {/* ── Body ── */}
      <div className="flex-1 max-w-screen-2xl mx-auto w-full flex overflow-hidden">

        {/* Desktop sidebar */}
        <aside className="hidden lg:flex flex-col w-72 xl:w-80 border-r border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 flex-shrink-0 sticky top-14 h-[calc(100vh-3.5rem)] overflow-hidden">
          {SidebarContent}
        </aside>

        {/* Mobile sidebar drawer */}
        {sidebarOpen && (
          <div className="lg:hidden fixed inset-0 z-40 flex">
            <div className="absolute inset-0 bg-black/50" onClick={() => setSidebarOpen(false)} />
            <aside className="relative w-80 max-w-[85vw] bg-white dark:bg-slate-900 h-full overflow-hidden flex flex-col">
              <div className="flex items-center justify-between px-4 py-3 border-b border-slate-200 dark:border-slate-800">
                <span className="font-bold text-slate-900 dark:text-slate-50">Nội dung khóa học</span>
                <button onClick={() => setSidebarOpen(false)} className="p-1 rounded text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800">
                  <X className="w-5 h-5" />
                </button>
              </div>
              {SidebarContent}
            </aside>
          </div>
        )}

        {/* ── Right panel ── */}
        <main className="flex-1 overflow-y-auto min-w-0">

          {/* ── STATS TAB ── */}
          {rightTab === "stats" && (
            <div className="p-4 sm:p-6 lg:p-8 max-w-3xl space-y-8">
              {/* Section title */}
              <div>
                <h2 className="text-xl font-bold text-slate-900 dark:text-slate-50">Thống kê của tôi</h2>
                <p className="text-sm text-slate-500 dark:text-slate-400 mt-0.5">
                  Tổng quan tiến độ và kết quả học tập trong khóa học này
                </p>
              </div>

              {/* KPI cards */}
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                <KpiCard
                  label="Tiến độ"
                  value={`${progressPct}%`}
                  sub={`${completedCount}/${totalMandatory} bài`}
                  accent="bg-blue-500"
                  pct={progressPct}
                />
                <KpiCard
                  label="Bài bắt buộc xong"
                  value={String(completedCount)}
                  sub={totalMandatory > 0 ? `trong ${totalMandatory} bài` : "Không có bài bắt buộc"}
                  accent="bg-emerald-500"
                  pct={totalMandatory > 0 ? (completedCount / totalMandatory) * 100 : 0}
                />
                <KpiCard
                  label="Quiz đã đạt"
                  value={quizScores.length > 0 ? `${passedQuizzes}/${quizScores.length}` : "—"}
                  sub={quizScores.length > 0 ? `${((passedQuizzes / quizScores.length) * 100).toFixed(0)}% tỷ lệ` : "Chưa có quiz"}
                  accent="bg-violet-500"
                  pct={quizScores.length > 0 ? (passedQuizzes / quizScores.length) * 100 : 0}
                />
                <KpiCard
                  label="Điểm TB quiz"
                  value={avgPct != null ? `${avgPct.toFixed(1)}%` : "—"}
                  sub={avgPct != null ? (avgPct >= 70 ? "Tốt" : "Cần cải thiện") : "Chưa làm quiz"}
                  accent={avgPct != null && avgPct >= 70 ? "bg-amber-400" : "bg-red-400"}
                  pct={avgPct ?? 0}
                />
              </div>

              {/* Progress section */}
              <section>
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-base font-bold text-slate-900 dark:text-slate-50">Tiến độ học tập</h3>
                  {progressDetail.filter(i => i.is_mandatory && !i.is_completed).length > 0 && (
                    <span className="flex items-center gap-1 text-xs text-orange-600 dark:text-orange-400">
                      <AlertCircle className="w-3.5 h-3.5" />
                      {progressDetail.filter(i => i.is_mandatory && !i.is_completed).length} bài còn lại
                    </span>
                  )}
                </div>

                {/* Overall bar */}
                <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-4 shadow-sm mb-4">
                  <div className="flex justify-between items-end mb-2">
                    <span className="text-2xl font-extrabold text-slate-900 dark:text-slate-50">{progressPct}%</span>
                    <span className="text-xs text-slate-500">{completedCount}/{totalMandatory} bài bắt buộc</span>
                  </div>
                  <div className="h-2 bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-blue-500 rounded-full transition-all duration-700"
                      style={{ width: `${Math.min(progressPct, 100)}%` }}
                    />
                  </div>
                  {progressPct === 100 && totalMandatory > 0 && (
                    <p className="text-xs text-emerald-600 dark:text-emerald-400 font-medium mt-2 flex items-center gap-1">
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      Hoàn thành tất cả nội dung bắt buộc!
                    </p>
                  )}
                </div>

                <ProgressList items={progressDetail} onMarkComplete={handleMarkComplete} />
              </section>

              {/* Quiz scores section */}
              <section>
                <h3 className="text-base font-bold text-slate-900 dark:text-slate-50 mb-4">Kết quả Quiz</h3>
                {statsLoading ? (
                  <div className="space-y-3">
                    {[0, 1, 2].map(i => (
                      <div key={i} className="h-20 bg-slate-100 dark:bg-slate-800 rounded-2xl animate-pulse" />
                    ))}
                  </div>
                ) : quizScores.length === 0 ? (
                  <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-8 text-center">
                    <HelpCircle className="w-8 h-8 text-slate-300 dark:text-slate-700 mx-auto mb-2" />
                    <p className="text-sm text-slate-500 dark:text-slate-400">Chưa có quiz nào trong khóa học.</p>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {quizScores.map(score => (
                      <QuizScoreCard key={score.quiz_id} score={score} />
                    ))}
                  </div>
                )}
              </section>
            </div>
          )}

          {/* ── LEARN TAB ── */}
          {rightTab === "learn" && (
            <>
              {activeContent ? (
                <div className="p-4 sm:p-6 lg:p-8 max-w-4xl">
                  {/* Badges */}
                  <div className="flex items-center gap-2 mb-5">
                    <ContentTypeBadge type={activeContent.type} />
                    {activeContent.is_mandatory && <Badge variant="yellow">Bắt buộc</Badge>}
                    {activeContent.is_mandatory && completedIds.has(activeContent.id) && (
                      <Badge variant="green">✓ Đã hoàn thành</Badge>
                    )}
                  </div>

                  {/* Title */}
                  <h2 className="text-2xl font-bold text-slate-900 dark:text-slate-50 mb-2">
                    {activeContent.title}
                  </h2>
                  {activeContent.description && (
                    <p className="text-slate-600 dark:text-slate-400 mb-6">{activeContent.description}</p>
                  )}
                  <div className="border-t border-slate-200 dark:border-slate-800 mb-6" />

                  {/* Viewer */}
                  <ContentViewer
                    content={activeContent}
                    userRole="STUDENT"
                    isCompleted={completedIds.has(activeContent.id)}
                    onComplete={() => handleMarkComplete(activeContent.id)}
                  />

                  {/* Manual complete button (non-quiz mandatory, not yet done) */}
                  {activeContent.is_mandatory &&
                   !completedIds.has(activeContent.id) &&
                   activeContent.type !== "QUIZ" && (
                    <div className="mt-8 pt-6 border-t border-slate-200 dark:border-slate-800">
                      <button
                        onClick={() => handleMarkComplete(activeContent.id)}
                        disabled={markingComplete}
                        className="flex items-center gap-2 px-5 py-2.5 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white rounded-xl font-semibold text-sm transition-all active:scale-95"
                      >
                        {markingComplete ? (
                          <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                        ) : (
                          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                          </svg>
                        )}
                        Đánh dấu đã hoàn thành
                      </button>
                      <p className="text-xs text-slate-400 dark:text-slate-500 mt-2">
                        Hoặc nội dung sẽ tự động đánh dấu sau khi bạn xem đủ thời gian.
                      </p>
                    </div>
                  )}

                  {/* Prev / Next navigation */}
                  <div className="mt-10 pt-6 border-t border-slate-200 dark:border-slate-800 flex items-center justify-between gap-4">
                    <PrevNextButtons
                      sections={sections}
                      sectionContents={sectionContents}
                      activeContent={activeContent}
                      onSelect={handleSelectContent}
                    />
                  </div>
                </div>
              ) : (
                /* Welcome screen */
                <div className="flex flex-col items-center justify-center h-full py-24 text-center px-8">
                  <div className="w-20 h-20 rounded-2xl bg-blue-50 dark:bg-blue-900/20 flex items-center justify-center mb-6">
                    <BookOpen className="w-10 h-10 text-blue-600 dark:text-blue-400" />
                  </div>
                  <h2 className="text-xl font-bold text-slate-900 dark:text-slate-50 mb-2">
                    Chào mừng đến với khóa học
                  </h2>
                  <p className="text-slate-600 dark:text-slate-400 max-w-sm mb-6">
                    {course?.description ?? "Chọn một bài học ở bên trái để bắt đầu học."}
                  </p>
                  <div className="flex items-center gap-3">
                    {sections.length > 0 && (
                      <button
                        className="px-5 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl font-semibold text-sm transition-all active:scale-95"
                        onClick={() => toggleSection(sections[0].id)}
                      >
                        Bắt đầu học ngay
                      </button>
                    )}
                    <button
                      className="flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700 rounded-xl transition-all sm:hidden"
                      onClick={() => handleTabSwitch("stats")}
                    >
                      <BarChart3 className="w-4 h-4" />
                      Xem thống kê
                    </button>
                  </div>
                </div>
              )}
            </>
          )}
        </main>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// PREV / NEXT NAVIGATION
// ─────────────────────────────────────────────────────────────────────────────

function PrevNextButtons({
  sections, sectionContents, activeContent, onSelect,
}: {
  sections: Section[];
  sectionContents: Record<number, Content[]>;
  activeContent: Content;
  onSelect: (c: Content) => void;
}) {
  const flat = sections.flatMap(s => sectionContents[s.id] ?? []);
  const idx  = flat.findIndex(c => c.id === activeContent.id);
  const prev = idx > 0 ? flat[idx - 1] : null;
  const next = idx < flat.length - 1 ? flat[idx + 1] : null;

  return (
    <>
      {prev ? (
        <button
          className="flex items-center gap-2 text-sm font-medium text-slate-600 dark:text-slate-400 hover:text-blue-600 dark:hover:text-blue-400 transition-colors"
          onClick={() => onSelect(prev)}
        >
          <ArrowLeft className="w-4 h-4" />
          <span className="hidden sm:inline">Bài trước:</span>
          <span className="truncate max-w-[160px]">{prev.title}</span>
        </button>
      ) : <div />}

      {next && (
        <button
          className="flex items-center gap-2 text-sm font-semibold text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300 transition-colors"
          onClick={() => onSelect(next)}
        >
          <span className="truncate max-w-[160px]">{next.title}</span>
          <span className="hidden sm:inline">: Bài tiếp</span>
          <ChevronRight className="w-4 h-4" />
        </button>
      )}
    </>
  );
}