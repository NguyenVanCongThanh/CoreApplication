"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import lmsService from "@/services/lmsService";
import ContentViewer from "@/components/lms/student/ContentViewer";
import ContentModal from "@/components/lms/teacher/ContentModal";
import EditContentModal from "@/components/lms/teacher/EditContentModal";
import BulkUploadModal from "@/components/lms/teacher/BulkUploadModal";
import { EditCourseModal } from "@/components/lms/teacher/EditCourseModal";
import { SectionModal } from "@/components/lms/teacher/SectionModal";
import { OverviewTab } from "@/components/lms/teacher/OverviewTab";
import { StudentsTab } from "@/components/lms/teacher/StudentTab";
import {
  ArrowLeft, Plus, Users, ChevronDown, ChevronRight,
  Trash2, Eye, CheckCircle2, XCircle,
  Edit3, Upload, Play, FileText, HelpCircle, File,
  MessageSquare, Megaphone, Image as ImageIcon
} from "lucide-react";
import {
  Card, TabBar, Badge, ContentTypeBadge,
  StatCard, PrimaryBtn, SecondaryBtn, GhostBtn,
  EmptyState, PageLoader, Alert, Spinner
} from "@/components/lms/shared";
import { Course, Section, Content } from "@/types";

type Tab = "overview" | "content" | "learners" | "quizzes" | "students";

// ─── Learner list tab ─────────────────────────────────────────────────────────

interface Learner {
  id: number;
  student_id: number;
  student_name: string;
  student_email: string;
  status: "WAITING" | "ACCEPTED" | "REJECTED";
  enrolled_at: string;
}

function LearnersTab({ courseId }: { courseId: number }) {
  const [learners, setLearners] = useState<Learner[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<"ALL"|"WAITING"|"ACCEPTED"|"REJECTED">("ALL");
  const [processing, setProcessing] = useState<number | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const f = filter === "ALL" ? undefined : filter as any;
      const data = await lmsService.getCourseLearners(courseId, f);
      setLearners(data ?? []);
    } finally { setLoading(false); }
  }, [courseId, filter]);

  useEffect(() => { load(); }, [filter]);

  const accept = async (enrollmentId: number) => {
    setProcessing(enrollmentId);
    try {
      await lmsService.acceptEnrollment(enrollmentId, courseId);
      setLearners(prev => prev.map(l => l.id === enrollmentId ? { ...l, status: "ACCEPTED" } : l));
    } finally { setProcessing(null); }
  };

  const reject = async (enrollmentId: number) => {
    if (!confirm("Từ chối yêu cầu này?")) return;
    setProcessing(enrollmentId);
    try {
      await lmsService.rejectEnrollment(enrollmentId, courseId);
      setLearners(prev => prev.map(l => l.id === enrollmentId ? { ...l, status: "REJECTED" } : l));
    } finally { setProcessing(null); }
  };

  const counts = {
    waiting:  learners.filter(l => l.status === "WAITING").length,
    accepted: learners.filter(l => l.status === "ACCEPTED").length,
    rejected: learners.filter(l => l.status === "REJECTED").length,
  };

  const filtered = filter === "ALL" ? learners : learners.filter(l => l.status === filter);

  return (
    <div className="space-y-5">
      {/* Mini stats */}
      <div className="grid grid-cols-3 gap-3">
        <StatCard label="Đã duyệt"    value={counts.accepted} icon={<CheckCircle2 className="w-4 h-4" />} accent="green" />
        <StatCard label="Chờ duyệt"   value={counts.waiting}  icon={<HelpCircle className="w-4 h-4" />}   accent="orange" />
        <StatCard label="Từ chối"     value={counts.rejected} icon={<XCircle className="w-4 h-4" />}      accent="red" />
      </div>

      {/* Filter tabs */}
      <TabBar
        tabs={[
          { id: "ALL",      label: "Tất cả",      badge: learners.length },
          { id: "WAITING",  label: "Chờ duyệt",   badge: counts.waiting },
          { id: "ACCEPTED", label: "Đã duyệt",    badge: counts.accepted },
          { id: "REJECTED", label: "Từ chối" },
        ]}
        active={filter}
        onChange={setFilter as any}
      />

      {/* List */}
      {loading ? <PageLoader /> : filtered.length === 0 ? (
        <EmptyState icon={<Users className="w-10 h-10" />} title="Không có học viên" />
      ) : (
        <div className="divide-y divide-slate-100 dark:divide-slate-800 rounded-2xl border border-slate-200 dark:border-slate-800 overflow-hidden">
          {filtered.map(l => (
            <div key={l.id} className="flex items-center gap-4 px-5 py-4 bg-white dark:bg-slate-900 hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors">
              <div className="w-9 h-9 rounded-full bg-slate-100 dark:bg-slate-800 flex items-center justify-center font-bold text-sm text-slate-600 dark:text-slate-400 flex-shrink-0">
                {l.student_name.charAt(0).toUpperCase()}
              </div>
              <div className="flex-1 min-w-0">
                <p className="font-semibold text-slate-900 dark:text-slate-50 truncate text-sm">{l.student_name}</p>
                <p className="text-xs text-slate-500 truncate">{l.student_email}</p>
              </div>
              <div className="flex items-center gap-2 flex-shrink-0">
                <Badge variant={l.status === "ACCEPTED" ? "green" : l.status === "WAITING" ? "yellow" : "red"}>
                  {l.status === "ACCEPTED" ? "Đã duyệt" : l.status === "WAITING" ? "Chờ duyệt" : "Từ chối"}
                </Badge>
                {l.status === "WAITING" && (
                  <>
                    <button onClick={() => accept(l.id)} disabled={processing === l.id}
                      className="w-8 h-8 rounded-lg bg-green-50 dark:bg-green-950/20 text-green-700 dark:text-green-400 hover:bg-green-50 dark:hover:bg-green-950/30 flex items-center justify-center transition-colors border border-green-200 dark:border-green-800">
                      {processing === l.id ? <Spinner className="w-4 h-4 border-2" /> : <CheckCircle2 className="w-4 h-4" />}
                    </button>
                    <button onClick={() => reject(l.id)} disabled={processing === l.id}
                      className="w-8 h-8 rounded-lg bg-red-50 dark:bg-red-950/20 text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-950/30 flex items-center justify-center transition-colors border border-red-200 dark:border-red-800">
                      <XCircle className="w-4 h-4" />
                    </button>
                  </>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Content tree tab ─────────────────────────────────────────────────────────

const CONTENT_ICON: Record<string, React.ReactNode> = {
  VIDEO:        <Play className="w-3.5 h-3.5" />,
  DOCUMENT:     <FileText className="w-3.5 h-3.5" />,
  IMAGE:        <ImageIcon className="w-3.5 h-3.5" />,
  TEXT:         <FileText className="w-3.5 h-3.5" />,
  QUIZ:         <HelpCircle className="w-3.5 h-3.5" />,
  FORUM:        <MessageSquare className="w-3.5 h-3.5" />,
  ANNOUNCEMENT: <Megaphone className="w-3.5 h-3.5" />,
};

interface ContentTabProps {
  courseId: number;
  sections: Section[];
  onSectionsChange: () => void;
}

function ContentTab({ courseId, sections, onSectionsChange }: ContentTabProps) {
  const [expanded, setExpanded] = useState<Set<number>>(new Set(sections.slice(0,1).map(s=>s.id)));
  const [sectionContents, setSectionContents] = useState<Record<number, Content[]>>({});
  const [loadingContent, setLoadingContent] = useState<Record<number, boolean>>({});

  const [showSectionModal, setShowSectionModal] = useState(false);
  const [editingSection, setEditingSection] = useState<Section | null>(null);
  const [showContentModal, setShowContentModal] = useState(false);
  const [showBulkModal, setShowBulkModal] = useState(false);
  const [showEditContentModal, setShowEditContentModal] = useState(false);
  const [showContentViewer, setShowContentViewer] = useState(false);
  const [selectedSectionId, setSelectedSectionId] = useState<number | null>(null);
  const [editingContent, setEditingContent] = useState<Content | null>(null);
  const [viewingContent, setViewingContent] = useState<Content | null>(null);
  const [deletingSection, setDeletingSection] = useState<number | null>(null);
  const [deletingContent, setDeletingContent] = useState<number | null>(null);

  const loadContents = useCallback(async (sectionId: number) => {
    if (sectionContents[sectionId]) return;
    setLoadingContent(prev => ({ ...prev, [sectionId]: true }));
    try {
      const res = await lmsService.listContent(sectionId);
      setSectionContents(prev => ({ ...prev, [sectionId]: res?.data ?? [] }));
    } finally {
      setLoadingContent(prev => ({ ...prev, [sectionId]: false }));
    }
  }, [sectionContents]);

  // Auto-load expanded sections
  useEffect(() => {
    expanded.forEach(id => loadContents(id));
  }, [expanded]);

  const toggle = (id: number) => {
    setExpanded(prev => {
      const n = new Set(prev);
      n.has(id) ? n.delete(id) : n.add(id);
      return n;
    });
  };

  const deleteSection = async (id: number) => {
    if (!confirm("Xóa chương này?")) return;
    setDeletingSection(id);
    try { await lmsService.deleteSection(id); onSectionsChange(); }
    finally { setDeletingSection(null); }
  };

  const deleteContent = async (contentId: number, sectionId: number) => {
    if (!confirm("Xóa nội dung này?")) return;
    setDeletingContent(contentId);
    try {
      await lmsService.deleteContent(contentId);
      setSectionContents(prev => ({
        ...prev,
        [sectionId]: (prev[sectionId] ?? []).filter(c => c.id !== contentId)
      }));
    } finally { setDeletingContent(null); }
  };

  const reloadSectionContent = async (sectionId: number) => {
    setLoadingContent(prev => ({ ...prev, [sectionId]: true }));
    try {
      const res = await lmsService.listContent(sectionId);
      setSectionContents(prev => ({ ...prev, [sectionId]: res?.data ?? [] }));
    } finally { setLoadingContent(prev => ({ ...prev, [sectionId]: false })); }
  };

  return (
    <div className="space-y-4">
      {/* Top action */}
      <div className="flex items-center justify-between">
        <p className="text-sm text-slate-500 dark:text-slate-500">{sections.length} chương</p>
        <PrimaryBtn
          size="sm"
          icon={<Plus className="w-4 h-4" />}
          onClick={() => { setEditingSection(null); setShowSectionModal(true); }}
        >
          Thêm chương
        </PrimaryBtn>
      </div>

      {sections.length === 0 ? (
        <EmptyState
          icon={<FileText className="w-10 h-10" />}
          title="Chưa có chương nào"
          description="Tạo chương đầu tiên để bắt đầu thêm nội dung."
          action={
            <PrimaryBtn
              size="sm"
              icon={<Plus className="w-4 h-4" />}
              onClick={() => setShowSectionModal(true)}
            >
              Tạo chương đầu tiên
            </PrimaryBtn>
          }
        />
      ) : (
        <div className="space-y-3">
          {sections.map((sec, i) => {
            const isExpanded = expanded.has(sec.id);
            const contents = sectionContents[sec.id] ?? [];
            const isLoadingC = loadingContent[sec.id];

            return (
              <div key={sec.id} className="rounded-2xl border border-slate-200 dark:border-slate-800 overflow-hidden bg-white dark:bg-slate-900">
                {/* Section header */}
                <div
                  className="flex items-center gap-3 px-5 py-4 bg-slate-50 dark:bg-slate-800/50 cursor-pointer hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
                  onClick={() => toggle(sec.id)}
                >
                  <div className="w-7 h-7 rounded-lg bg-blue-50 dark:bg-blue-950/20 text-blue-600 dark:text-blue-400 flex items-center justify-center text-xs font-bold flex-shrink-0 border border-blue-200 dark:border-blue-800">
                    {i + 1}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="font-semibold text-slate-900 dark:text-slate-50 truncate">{sec.title}</p>
                    <p className="text-xs text-slate-500 mt-0.5">
                      {isExpanded ? `${contents.length} nội dung` : sec.description || "Nhấn để xem nội dung"}
                    </p>
                  </div>
                  {/* Section actions */}
                  <div className="flex items-center gap-1" onClick={e => e.stopPropagation()}>
                    <button
                      className="p-1.5 rounded-lg hover:bg-white dark:hover:bg-slate-700 text-slate-500 transition-colors"
                      onClick={() => {
                        setSelectedSectionId(sec.id);
                        setShowContentModal(true);
                      }}
                      title="Thêm nội dung"
                    >
                      <Plus className="w-4 h-4" />
                    </button>
                    <button
                      className="p-1.5 rounded-lg hover:bg-white dark:hover:bg-slate-700 text-slate-500 transition-colors"
                      onClick={() => {
                        setSelectedSectionId(sec.id);
                        setShowBulkModal(true);
                      }}
                      title="Bulk upload"
                    >
                      <Upload className="w-4 h-4" />
                    </button>
                    <button
                      className="p-1.5 rounded-lg hover:bg-white dark:hover:bg-slate-700 text-slate-500 transition-colors"
                      onClick={() => { setEditingSection(sec); setShowSectionModal(true); }}
                      title="Sửa chương"
                    >
                      <Edit3 className="w-4 h-4" />
                    </button>
                    <button
                      disabled={deletingSection === sec.id}
                      className="p-1.5 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/20 text-red-500 transition-colors"
                      onClick={() => deleteSection(sec.id)}
                      title="Xóa chương"
                    >
                      {deletingSection === sec.id ? <Spinner className="w-4 h-4 border-2" /> : <Trash2 className="w-4 h-4" />}
                    </button>
                  </div>
                  {isExpanded ? <ChevronDown className="w-4 h-4 text-slate-400 flex-shrink-0" /> : <ChevronRight className="w-4 h-4 text-slate-400 flex-shrink-0" />}
                </div>

                {/* Content list */}
                {isExpanded && (
                  <div>
                    {isLoadingC ? (
                      <div className="px-5 py-4">
                        <div className="space-y-2">
                          {[0,1,2].map(k => <div key={k} className="h-8 bg-slate-100 dark:bg-slate-800 rounded-lg animate-pulse" />)}
                        </div>
                      </div>
                    ) : contents.length === 0 ? (
                      <div className="px-5 py-6 text-center">
                        <p className="text-sm text-slate-400">Chưa có nội dung. Nhấn + để thêm.</p>
                      </div>
                    ) : (
                      <div className="divide-y divide-slate-100 dark:divide-slate-800">
                        {contents.map((c, ci) => (
                          <div key={c.id} className="flex items-center gap-3 px-5 py-3 group hover:bg-slate-50 dark:hover:bg-slate-800/30 transition-colors">
                            <span className="text-slate-400 dark:text-slate-500 flex-shrink-0 w-4 text-xs text-right">{ci+1}</span>
                            <span className="text-slate-400 dark:text-slate-500 flex-shrink-0">
                              {CONTENT_ICON[c.type] ?? <File className="w-3.5 h-3.5" />}
                            </span>
                            <p className="flex-1 text-sm font-medium text-slate-800 dark:text-slate-200 truncate">{c.title}</p>
                            <ContentTypeBadge type={c.type} />
                            {c.is_mandatory && <Badge variant="yellow">Bắt buộc</Badge>}

                            {/* Content actions (hidden until hover) */}
                            <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                              <button
                                className="p-1.5 rounded-lg hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-500"
                                onClick={() => { setViewingContent(c); setShowContentViewer(true); }}
                                title="Xem"
                              >
                                <Eye className="w-3.5 h-3.5" />
                              </button>
                              <button
                                className="p-1.5 rounded-lg hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-500"
                                onClick={() => { setEditingContent(c); setShowEditContentModal(true); }}
                                title="Sửa"
                              >
                                <Edit3 className="w-3.5 h-3.5" />
                              </button>
                              <button
                                disabled={deletingContent === c.id}
                                className="p-1.5 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/20 text-red-500"
                                onClick={() => deleteContent(c.id, sec.id)}
                                title="Xóa"
                              >
                                {deletingContent === c.id ? <Spinner className="w-3.5 h-3.5 border-2" /> : <Trash2 className="w-3.5 h-3.5" />}
                              </button>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Modals */}
      {showSectionModal && (
        <SectionModal
          courseId={courseId}
          section={editingSection}
          existingSections={sections}
          onClose={() => { setShowSectionModal(false); setEditingSection(null); }}
          onSuccess={() => { setShowSectionModal(false); setEditingSection(null); onSectionsChange(); }}
        />
      )}

      {showContentModal && selectedSectionId && (
        <ContentModal
          sectionId={selectedSectionId}
          existingContents={sectionContents[selectedSectionId] ?? []}
          onClose={() => { setShowContentModal(false); setSelectedSectionId(null); }}
          onSuccess={() => {
            setShowContentModal(false);
            if (selectedSectionId) reloadSectionContent(selectedSectionId);
            setSelectedSectionId(null);
          }}
        />
      )}

      {showBulkModal && selectedSectionId && (
        <BulkUploadModal
          sectionId={selectedSectionId}
          onClose={() => { setShowBulkModal(false); setSelectedSectionId(null); }}
          onSuccess={() => {
            setShowBulkModal(false);
            if (selectedSectionId) reloadSectionContent(selectedSectionId);
            setSelectedSectionId(null);
          }}
        />
      )}

      {showEditContentModal && editingContent && (
        <EditContentModal
          content={editingContent}
          onClose={() => { setShowEditContentModal(false); setEditingContent(null); }}
          onSuccess={() => {
            setShowEditContentModal(false);
            reloadSectionContent(editingContent.section_id);
            setEditingContent(null);
          }}
        />
      )}

      {showContentViewer && viewingContent && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white dark:bg-slate-900 rounded-2xl max-w-4xl w-full max-h-[90vh] overflow-y-auto">
            <div className="sticky top-0 bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 px-6 py-4 flex items-center justify-between">
              <h3 className="font-bold text-slate-900 dark:text-slate-50">{viewingContent.title}</h3>
              <button onClick={() => { setShowContentViewer(false); setViewingContent(null); }}
                className="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-500">
                ✕
              </button>
            </div>
            <div className="p-6">
              <ContentViewer content={viewingContent} userRole="TEACHER" />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Main page ─────────────────────────────────────────────────────────────────

export default function TeacherCourseDetailPage() {
  const { courseId } = useParams<{ courseId: string }>();
  const router = useRouter();
  const id = Number(courseId);

  const [course, setCourse] = useState<Course | null>(null);
  const [sections, setSections] = useState<Section[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [tab, setTab] = useState<Tab>("overview");
  const [showEditModal, setShowEditModal] = useState(false);
  const [publishing, setPublishing] = useState(false);

  const loadCourse = useCallback(async () => {
    try {
      const res = await lmsService.getCourse(id);
      setCourse(res?.data ?? null);
    } catch { setError("Không thể tải thông tin khóa học."); }
  }, [id]);

  const loadSections = useCallback(async () => {
    try {
      const res = await lmsService.listSections(id);
      setSections(res?.data ?? []);
    } catch {}
  }, [id]);

  useEffect(() => {
    (async () => {
      setLoading(true);
      await Promise.all([loadCourse(), loadSections()]);
      setLoading(false);
    })();
  }, [id]);

  const handlePublish = async () => {
    if (!confirm("Xuất bản khóa học này?")) return;
    setPublishing(true);
    try {
      await lmsService.publishCourse(id);
      await loadCourse();
    } catch { setError("Không thể xuất bản."); }
    finally { setPublishing(false); }
  };

  if (loading) return <PageLoader message="Đang tải khóa học..." />;
  if (!course) return <div className="p-8 text-center text-slate-500">Không tìm thấy khóa học.</div>;

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950">
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">

        {/* Breadcrumb + header */}
        <div>
          <GhostBtn
            size="sm"
            icon={<ArrowLeft className="w-4 h-4" />}
            onClick={() => router.push("/lms/teacher/courses")}
            className="mb-4"
          >
            Quay lại
          </GhostBtn>

          <Card className="p-6">
            <div className="flex items-start justify-between gap-4 flex-wrap">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-2 flex-wrap">
                  <Badge variant={course.status === "PUBLISHED" ? "green" : "yellow"}>
                    {course.status === "PUBLISHED" ? "Đã xuất bản" : "Nháp"}
                  </Badge>
                  {course.level && <Badge variant="gray">{course.level}</Badge>}
                  {course.category && <Badge variant="blue">{course.category}</Badge>}
                </div>
                <h1 className="text-2xl font-extrabold text-slate-900 dark:text-slate-50 mb-1">
                  {course.title}
                </h1>
                <p className="text-slate-600 dark:text-slate-400 text-sm">
                  {course.description || "Chưa có mô tả."}
                </p>
              </div>

              <div className="flex items-center gap-2 flex-shrink-0">
                {course.status === "DRAFT" && (
                  <PrimaryBtn
                    size="sm"
                    loading={publishing}
                    icon={<Eye className="w-4 h-4" />}
                    onClick={handlePublish}
                  >
                    Xuất bản
                  </PrimaryBtn>
                )}
                <SecondaryBtn
                  size="sm"
                  icon={<Edit3 className="w-4 h-4" />}
                  onClick={() => setShowEditModal(true)}
                >
                  Chỉnh sửa
                </SecondaryBtn>
              </div>
            </div>
          </Card>
        </div>

        {error && <Alert type="error">{error}</Alert>}

        {/* Tabs */}
        <Card className="overflow-hidden">
          <div className="px-6 pt-5 border-b border-slate-200 dark:border-slate-800">
            <div className="pb-4">
              <TabBar
                tabs={[
                  { id: "overview"  as Tab, label: "Tổng quan" },
                  { id: "content"   as Tab, label: "Nội dung", badge: sections.length },
                  { id: "learners"  as Tab, label: "Học viên" },
                  { id: "students"  as Tab, label: "Tiến độ học tập"},
                ]}
                active={tab}
                onChange={setTab}
              />
            </div>
          </div>

          <div className="p-6">
            {tab === "overview" && (
              <OverviewTab course={course} sections={sections} />
            )}
            {tab === "content" && (
              <ContentTab
                courseId={id}
                sections={sections}
                onSectionsChange={() => { loadSections(); }}
              />
            )}
            {tab === "learners" && (
              <LearnersTab courseId={id} />
            )}
            {tab === "students" && (
              <StudentsTab courseId={id} />
            )}
          </div>
        </Card>

      </div>

      {/* Edit course modal */}
      {showEditModal && (
        <EditCourseModal
          course={course}
          onClose={() => setShowEditModal(false)}
          onSuccess={() => { setShowEditModal(false); loadCourse(); }}
        />
      )}
    </div>
  );
}