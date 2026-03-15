"use client";

/**
 * Student Course Detail — Split Layout
 *
 * UX priority: content is visible immediately.
 *
 * Layout (desktop):
 *   ┌──────────────────────────────────────────────────────┐
 *   │ Header (course title + breadcrumb)                   │
 *   ├─────────────────────┬────────────────────────────────┤
 *   │ Left sidebar        │ Right: content viewer          │
 *   │ ─────────────       │ ─────────────────────────      │
 *   │ Section 1  [▼]      │ <ContentViewer />              │
 *   │   · Item 1 [active] │                                │
 *   │   · Item 2          │                                │
 *   │ Section 2  [▶]      │                                │
 *   └─────────────────────┴────────────────────────────────┘
 *
 * Mobile: sidebar collapses into a drawer.
 */

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import lmsService from "@/services/lmsService";
import ContentViewer from "@/components/lms/student/ContentViewer";
import {
  ArrowLeft, ChevronDown, ChevronRight, Menu, X,
  Play, FileText, Image as ImageIcon, HelpCircle,
  MessageSquare, Megaphone, File as FileIcon, BookOpen
} from "lucide-react";
import {
  Badge, ContentTypeBadge, PageLoader,
  GhostBtn, ProgressBar
} from "@/components/lms/shared";
import { Content, Course, Section } from "@/types";
import { cn } from "@/lib/utils";

// ─── Content type icon (compact) ──────────────────────────────────────────────

const CONTENT_ICON: Record<string, React.ReactNode> = {
  VIDEO:        <Play         className="w-3.5 h-3.5" />,
  DOCUMENT:     <FileText     className="w-3.5 h-3.5" />,
  IMAGE:        <ImageIcon    className="w-3.5 h-3.5" />,
  TEXT:         <FileText     className="w-3.5 h-3.5" />,
  QUIZ:         <HelpCircle   className="w-3.5 h-3.5" />,
  FORUM:        <MessageSquare className="w-3.5 h-3.5"/>,
  ANNOUNCEMENT: <Megaphone    className="w-3.5 h-3.5" />,
};

// ─── Sidebar section item ─────────────────────────────────────────────────────

interface SidebarSectionProps {
  section: Section;
  index: number;
  contents: Content[];
  loadingContents: boolean;
  isExpanded: boolean;
  onToggle: () => void;
  activeContentId: number | null;
  onSelectContent: (c: Content) => void;
}

function SidebarSection({
  section, index, contents, loadingContents,
  isExpanded, onToggle, activeContentId, onSelectContent
}: SidebarSectionProps) {
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
            <p className="text-xs text-slate-500 mt-0.5">{contents.length} nội dung</p>
          )}
        </div>
        {isExpanded
          ? <ChevronDown className="w-4 h-4 text-slate-400 flex-shrink-0" />
          : <ChevronRight className="w-4 h-4 text-slate-400 flex-shrink-0" />}
      </button>

      {/* Content items */}
      {isExpanded && (
        <div className="pb-1">
          {loadingContents && !contents.length ? (
            <div className="px-4 py-3">
              <div className="space-y-2">
                {[0,1,2].map(i => (
                  <div key={i} className="h-8 bg-slate-100 dark:bg-slate-800 rounded-lg animate-pulse" />
                ))}
              </div>
            </div>
          ) : contents.length === 0 ? (
            <p className="px-4 py-3 text-xs text-slate-400">Chưa có nội dung</p>
          ) : (
            contents.map((c, i) => {
              const isActive = c.id === activeContentId;
              return (
                <button
                  key={c.id}
                  className={cn(
                    "w-full flex items-center gap-3 px-4 py-2.5 text-left transition-colors",
                    isActive
                      ? "bg-blue-50 dark:bg-blue-900/20 border-r-2 border-blue-600"
                      : "hover:bg-slate-50 dark:hover:bg-slate-800/50"
                  )}
                  onClick={() => onSelectContent(c)}
                >
                  <span className={cn(
                    "flex-shrink-0",
                    isActive ? "text-blue-600 dark:text-blue-400" : "text-slate-400 dark:text-slate-500"
                  )}>
                    {CONTENT_ICON[c.type] ?? <FileIcon className="w-3.5 h-3.5" />}
                  </span>
                  <span className={cn(
                    "text-sm truncate flex-1",
                    isActive ? "font-semibold text-blue-700 dark:text-blue-300" : "text-slate-700 dark:text-slate-300"
                  )}>
                    {i + 1}. {c.title}
                  </span>
                  {c.is_mandatory && (
                    <span className="w-1.5 h-1.5 rounded-full bg-orange-400 flex-shrink-0" title="Bắt buộc" />
                  )}
                </button>
              );
            })
          )}
        </div>
      )}
    </div>
  );
}

// ─── Main page ─────────────────────────────────────────────────────────────────

export default function StudentCourseDetailPage() {
  const { courseId } = useParams<{ courseId: string }>();
  const router = useRouter();
  const id = Number(courseId);

  const [course, setCourse] = useState<Course | null>(null);
  const [sections, setSections] = useState<Section[]>([]);
  const [sectionContents, setSectionContents] = useState<Record<number, Content[]>>({});
  const [loadingSection, setLoadingSection] = useState<Record<number, boolean>>({});
  const [expandedSections, setExpandedSections] = useState<Set<number>>(new Set());
  const [activeContent, setActiveContent] = useState<Content | null>(null);
  const [loadingPage, setLoadingPage] = useState(true);
  const [sidebarOpen, setSidebarOpen] = useState(false);   // mobile drawer

  // ── Load course + sections ────────────────────────────────────────────────

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

        // Auto-expand first section and load its contents immediately
        if (secs.length > 0) {
          const first = secs[0];
          setExpandedSections(new Set([first.id]));
          await loadSectionContents(first.id, true); // load & auto-select first item
        }
      } catch {
        router.back();
      } finally {
        setLoadingPage(false);
      }
    })();
  }, [id]);

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
      const res = await lmsService.listContent(sectionId);
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
    setExpandedSections(prev => {
      const next = new Set(prev);
      if (next.has(sectionId)) { next.delete(sectionId); }
      else {
        next.add(sectionId);
        loadSectionContents(sectionId);
      }
      return next;
    });
  }, [loadSectionContents]);

  // Total contents count
  const totalContents = Object.values(sectionContents).reduce((s, arr) => s + arr.length, 0);
  const completedCount = 0; // TODO: track progress via API

  if (loadingPage) return <PageLoader message="Đang tải khóa học..." />;

  // ── Sidebar JSX ───────────────────────────────────────────────────────────

  const SidebarContent = (
    <div className="h-full flex flex-col">
      {/* Sidebar header */}
      <div className="px-4 pt-5 pb-4 border-b border-slate-200 dark:border-slate-800">
        <p className="text-xs font-semibold text-slate-500 dark:text-slate-500 uppercase tracking-wider mb-2">
          Nội dung khóa học
        </p>
        {totalContents > 0 && (
          <>
            <ProgressBar
              value={completedCount}
              max={totalContents}
              color="blue"
              showPercent={false}
              className="mb-1"
            />
            <p className="text-xs text-slate-500">
              {completedCount}/{totalContents} bài đã hoàn thành
            </p>
          </>
        )}
      </div>

      {/* Sections */}
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
              loadingContents={!!loadingSection[sec.id]}
              isExpanded={expandedSections.has(sec.id)}
              onToggle={() => toggleSection(sec.id)}
              activeContentId={activeContent?.id ?? null}
              onSelectContent={c => { setActiveContent(c); setSidebarOpen(false); }}
            />
          ))
        )}
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 flex flex-col">
      {/* ── Top bar ── */}
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
          {/* Mobile: sidebar toggle */}
          <button
            className="lg:hidden p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-600 dark:text-slate-400"
            onClick={() => setSidebarOpen(true)}
          >
            <Menu className="w-5 h-5" />
          </button>
        </div>
      </header>

      {/* ── Body: sidebar + viewer ── */}
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

        {/* Content area */}
        <main className="flex-1 overflow-y-auto min-w-0">
          {activeContent ? (
            <div className="p-4 sm:p-6 lg:p-8 max-w-4xl">
              {/* Content breadcrumb */}
              <div className="flex items-center gap-2 mb-5">
                <ContentTypeBadge type={activeContent.type} />
                {activeContent.is_mandatory && <Badge variant="yellow">Bắt buộc</Badge>}
              </div>

              {/* Content title */}
              <h2 className="text-2xl font-bold text-slate-900 dark:text-slate-50 mb-2">
                {activeContent.title}
              </h2>
              {activeContent.description && (
                <p className="text-slate-600 dark:text-slate-400 mb-6">{activeContent.description}</p>
              )}

              {/* Divider */}
              <div className="border-t border-slate-200 dark:border-slate-800 mb-6" />

              {/* Viewer */}
              <ContentViewer content={activeContent} userRole="STUDENT" />

              {/* Navigation: prev / next */}
              <div className="mt-10 pt-6 border-t border-slate-200 dark:border-slate-800 flex items-center justify-between gap-4">
                <PrevNextButtons
                  sections={sections}
                  sectionContents={sectionContents}
                  activeContent={activeContent}
                  onSelect={c => setActiveContent(c)}
                />
              </div>
            </div>
          ) : (
            // Welcome screen when no content selected
            <div className="flex flex-col items-center justify-center h-full py-24 text-center px-8">
              <div className="w-20 h-20 rounded-2xl bg-blue-50 dark:bg-blue-900/20 flex items-center justify-center mb-6">
                <BookOpen className="w-10 h-10 text-blue-600 dark:text-blue-400" />
              </div>
              <h2 className="text-xl font-bold text-slate-900 dark:text-slate-50 mb-2">
                Chào mừng đến với khóa học
              </h2>
              <p className="text-slate-600 dark:text-slate-400 max-w-sm">
                {course?.description ?? "Chọn một bài học ở bên trái để bắt đầu học."}
              </p>
              {sections.length > 0 && (
                <button
                  className="mt-6 px-5 py-2.5 bg-blue-600 text-white rounded-xl font-semibold hover:bg-blue-700 transition-colors"
                  onClick={() => {
                    const first = sections[0];
                    toggleSection(first.id);
                  }}
                >
                  Bắt đầu học ngay
                </button>
              )}
            </div>
          )}
        </main>
      </div>
    </div>
  );
}

// ─── Prev / Next navigation ───────────────────────────────────────────────────

function PrevNextButtons({
  sections, sectionContents, activeContent, onSelect
}: {
  sections: Section[];
  sectionContents: Record<number, Content[]>;
  activeContent: Content;
  onSelect: (c: Content) => void;
}) {
  // Flatten all contents in order
  const flat: Content[] = sections.flatMap(s => sectionContents[s.id] ?? []);
  const idx = flat.findIndex(c => c.id === activeContent.id);
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
          <span className="hidden sm:inline">:Bài tiếp</span>
          <ChevronRight className="w-4 h-4" />
        </button>
      )}
    </>
  );
}