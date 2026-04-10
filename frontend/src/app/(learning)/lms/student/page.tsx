"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { getCookie } from "@/utils/cookies";
import { lmsService } from "@/services/lmsService";
import {
  BookOpen, Clock, CheckCircle2,
  ChevronRight, Search, RefreshCw,
  LogOut, Home
} from "lucide-react";
import {
  StatCard, Card, TabBar, CourseCard,
  ProgressBar, Badge, PrimaryBtn,GhostBtn,
  EmptyState, PageLoader, Alert
} from "@/components/lms/shared";
import { Course, Enrollment } from "@/types";

type Tab = "my-courses" | "discover";

// ─── Stats row ────────────────────────────────────────────────────────────────

function LearningStats({ enrollments }: { enrollments: Enrollment[] }) {
  const accepted = enrollments.filter(e => e.status === "ACCEPTED");

  return (
    <div className="grid grid-cols-3 lg:grid-cols-3 gap-4">
      <StatCard
        label="Đã đăng ký"
        value={accepted.length}
        sub="khóa học"
        icon={<BookOpen className="w-5 h-5" />}
        accent="blue"
      />
      <StatCard
        label="Đang học"
        value={accepted.filter(e => (e.progress_percent || 0) < 100).length}
        sub="khóa đang tiến hành"
        icon={<Clock className="w-5 h-5" />}
        accent="orange"
      />
      <StatCard
        label="Hoàn thành"
        value={accepted.filter(e => (e.progress_percent || 0) === 100).length}
        sub="khóa học"
        icon={<CheckCircle2 className="w-5 h-5" />}
        accent="green"
      />
    </div>
  );
}

// ─── Enrolled course item ─────────────────────────────────────────────────────

function EnrolledCourseItem({
  enrollment,
  onOpen
}: { enrollment: Enrollment; onOpen: (id: number) => void }) {
  return (
    <div
      className="flex items-center gap-4 p-4 rounded-xl hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors cursor-pointer group"
      onClick={() => onOpen(enrollment.course_id)}
    >
      {/* Icon */}
      <div className="w-12 h-12 rounded-xl bg-blue-50 dark:bg-blue-900/20 flex items-center justify-center flex-shrink-0">
        <BookOpen className="w-6 h-6 text-blue-600 dark:text-blue-400" />
      </div>

      {/* Info */}
      <div className="flex-1 min-w-0">
        <p className="font-semibold text-slate-900 dark:text-slate-50 truncate">
          {enrollment.course_title ?? `Khóa học #${enrollment.course_id}`}
        </p>
        {enrollment.teacher_name && (
          <p className="text-xs text-slate-500 dark:text-slate-500 mt-0.5">
            {enrollment.teacher_name}
          </p>
        )}
        <ProgressBar value={enrollment.progress_percent || 0} max={100} color="blue" showPercent={true} className="mt-2" />
      </div>

      {/* Arrow */}
      <ChevronRight className="w-4 h-4 text-slate-400 group-hover:text-blue-600 transition-colors flex-shrink-0" />
    </div>
  );
}

// ─── Discover card ────────────────────────────────────────────────────────────

function DiscoverSection({
  courses,
  enrolling,
  enrolledIds,
  onEnroll,
}: {
  courses: Course[];
  enrolling: number | null;
  enrolledIds: Set<number>;
  onEnroll: (id: number) => void;
}) {
  const [search, setSearch] = useState("");
  const filtered = courses.filter(c =>
    c.title.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-5">
      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
        <input
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Tìm kiếm khóa học..."
          className="w-full pl-10 pr-4 py-2.5 border border-slate-300 dark:border-slate-700 rounded-xl text-sm
                     bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-slate-100
                     placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
        />
      </div>

      {filtered.length === 0 ? (
        <EmptyState
          icon={<BookOpen className="w-12 h-12" />}
          title="Chưa có khóa học"
          description="Hiện chưa có khóa học nào được xuất bản."
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
          {filtered.map(course => {
            const enrolled = enrolledIds.has(course.id);
            return (
              <CourseCard
                key={course.id}
                id={course.id}
                title={course.title}
                description={course.description}
                category={course.category}
                level={course.level}
                teacherName={course.teacher_name}
                thumbnailUrl={course.thumbnail_url}
                actions={
                  enrolled ? (
                    <Badge variant="green">Đã đăng ký</Badge>
                  ) : (
                    <PrimaryBtn
                      size="sm"
                      loading={enrolling === course.id}
                      onClick={e => { e.stopPropagation(); onEnroll(course.id); }}
                    >
                      Đăng ký
                    </PrimaryBtn>
                  )
                }
              />
            );
          })}
        </div>
      )}
    </div>
  );
}

// ─── Main page ────────────────────────────────────────────────────────────────

export default function StudentDashboard() {
  const router = useRouter();
  const [userName, setUserName] = useState("");
  const [tab, setTab] = useState<Tab>("my-courses");

  const [allEnrollments, setAllEnrollments] = useState<Enrollment[]>([]);
  const [acceptedEnrollments, setAcceptedEnrollments] = useState<Enrollment[]>([]);
  const [publishedCourses, setPublishedCourses] = useState<Course[]>([]);

  const [loadingEnrolled, setLoadingEnrolled] = useState(true);
  const [loadingDiscover, setLoadingDiscover] = useState(false);

  const [enrolling, setEnrolling] = useState<number | null>(null);
  const [error, setError] = useState("");

  // ── Init ──────────────────────────────────────────────────────────────────

  useEffect(() => {
    const role = sessionStorage.getItem("lms_selected_role");
    if (role !== "STUDENT") { router.push("/lms"); return; }
    setUserName(getCookie("userName") || "bạn");
    loadAllEnrollments();
  }, []);

  const loadAllEnrollments = useCallback(async () => {
    setLoadingEnrolled(true);
    try {
      const [accepted] = await Promise.all([
        lmsService.getMyEnrollments("ACCEPTED"),
      ]);
      setAcceptedEnrollments(accepted || []);
      setAllEnrollments([...(accepted || [])]);
    } catch {
      setError("Không thể tải dữ liệu. Vui lòng thử lại.");
    } finally {
      setLoadingEnrolled(false);
    }
  }, []);

  const loadDiscover = useCallback(async () => {
    if (publishedCourses.length > 0) return;
    setLoadingDiscover(true);
    try {
      const data = await lmsService.listPublishedCourses({ page_size: 50 });
      setPublishedCourses(data || []);
    } catch {
      setError("Không thể tải danh sách khóa học.");
    } finally {
      setLoadingDiscover(false);
    }
  }, [publishedCourses.length]);

  useEffect(() => {
    if (tab === "discover") loadDiscover();
  }, [tab]);

  // ── Actions ───────────────────────────────────────────────────────────────

  const handleEnroll = async (courseId: number) => {
    setEnrolling(courseId);
    try {
      await lmsService.enrollCourse(courseId);
      await loadAllEnrollments();
    } catch (e: any) {
      setError(e?.response?.data?.message || "Đăng ký thất bại.");
    } finally {
      setEnrolling(null);
    }
  };

  const enrolledIds = new Set(allEnrollments.map(e => e.course_id));

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">

        {/* ── Header ── */}
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-sm text-slate-500 dark:text-slate-500 uppercase tracking-wider font-semibold mb-1">
              Học viên
            </p>
            <h1 className="text-3xl font-extrabold text-slate-900 dark:text-slate-50 leading-tight">
              Xin chào, {userName} 👋
            </h1>
            <p className="text-slate-600 dark:text-slate-400 mt-1">
              Tiếp tục lộ trình học tập của bạn hôm nay.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <GhostBtn
              size="sm"
              icon={<Home className="w-4 h-4" />}
              onClick={() => router.push("/")}
            >
              Trang chủ
            </GhostBtn>
            <GhostBtn
              size="sm"
              icon={<LogOut className="w-4 h-4" />}
              onClick={() => { sessionStorage.removeItem("lms_selected_role"); router.push("/lms"); }}
            >
              Đổi vai trò
            </GhostBtn>
          </div>
        </div>

        {/* ── Error alert ── */}
        {error && <Alert type="error">{error}</Alert>}

        {/* ── Stats row ── */}
        {loadingEnrolled ? (
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            {[0,1,2,3].map(i => (
              <div key={i} className="h-24 bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 animate-pulse" />
            ))}
          </div>
        ) : (
          <LearningStats enrollments={allEnrollments} />
        )}

        {/* ── Tab section ── */}
        <Card className="overflow-hidden">
          {/* Tab bar */}
          <div className="px-6 pt-5 pb-0 border-b border-slate-200 dark:border-slate-800">
            <div className="flex items-center justify-between pb-4">
              <TabBar
                tabs={[
                  { id: "my-courses" as Tab, label: "Khóa học của tôi", badge: acceptedEnrollments.length },
                  { id: "discover"  as Tab, label: "Khám phá" }
                ]}
                active={tab}
                onChange={setTab}
              />
              <GhostBtn
                size="sm"
                icon={<RefreshCw className="w-3.5 h-3.5" />}
                onClick={loadAllEnrollments}
              >
                Làm mới
              </GhostBtn>
            </div>
          </div>

          {/* Tab content */}
          <div className="p-6">
            {/* ── My courses ── */}
            {tab === "my-courses" && (
              loadingEnrolled ? <PageLoader /> :
              acceptedEnrollments.length === 0 ? (
                <EmptyState
                  icon={<BookOpen className="w-14 h-14" />}
                  title="Chưa học khóa nào"
                  description="Hãy khám phá và đăng ký khóa học phù hợp với bạn."
                  action={
                    <PrimaryBtn icon={<Search className="w-4 h-4" />} onClick={() => setTab("discover")}>
                      Khám phá khóa học
                    </PrimaryBtn>
                  }
                />
              ) : (
                <div className="space-y-1 divide-y divide-slate-100 dark:divide-slate-800">
                  {acceptedEnrollments.map(en => (
                    <EnrolledCourseItem
                      key={en.id}
                      enrollment={en}
                      onOpen={id => router.push(`/lms/student/courses/${id}`)}
                    />
                  ))}
                </div>
              )
            )}

            {/* ── Discover ── */}
            {tab === "discover" && (
              loadingDiscover ? <PageLoader /> :
              <DiscoverSection
                courses={publishedCourses}
                enrolling={enrolling}
                enrolledIds={enrolledIds}
                onEnroll={handleEnroll}
              />
            )}
          </div>
        </Card>

      </div>
    </div>
  );
}