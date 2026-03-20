"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { getCookie } from "@/utils/cookies";
import {
  BookOpen, Users, CheckCircle2, Clock,
  RefreshCw, Settings, Plus,
  Home, LogOut, BarChart3,
  Shield
} from "lucide-react";
import {
  StatCard, Card, SectionHeader, ProgressBar,
  SecondaryBtn, GhostBtn, PageLoader, Alert
} from "@/components/lms/shared";

interface DashboardStats {
  totalCourses: number;
  publishedCourses: number;
  draftCourses: number;
  totalEnrollments: number;
  pendingEnrollments: number;
  totalStudents: number;
  totalTeachers: number;
  activeStudents: number;
}

// ─── Action card (grid item) ──────────────────────────────────────────────────

function ActionItem({
  icon, label, description, onClick, badge, accent = false
}: {
  icon: React.ReactNode; label: string; description: string;
  onClick: () => void; badge?: number; accent?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      className={`relative flex flex-col gap-3 p-5 rounded-2xl border text-left transition-all active:scale-95 hover:shadow-sm
        ${accent
          ? "border-blue-200 dark:border-blue-800 bg-blue-50/50 dark:bg-blue-900/10 hover:border-blue-400"
          : "border-slate-200 dark:border-slate-800 hover:border-slate-300 dark:hover:border-slate-700"
        }`}
    >
      {badge !== undefined && badge > 0 && (
        <span className="absolute -top-2 -right-2 w-6 h-6 bg-red-500 text-white text-xs font-bold rounded-full flex items-center justify-center z-10">
          {badge > 99 ? "99+" : badge}
        </span>
      )}
      <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${accent ? "bg-blue-50 dark:bg-blue-950/20 text-blue-600 dark:text-blue-400 border border-blue-200 dark:border-blue-800" : "bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 border border-slate-200 dark:border-slate-700"}`}>
        {icon}
      </div>
      <div>
        <p className="font-semibold text-slate-800 dark:text-slate-200 text-sm">{label}</p>
        <p className="text-xs text-slate-500 dark:text-slate-500 mt-0.5">{description}</p>
      </div>
    </button>
  );
}

// ─── Main ──────────────────────────────────────────────────────────────────────

export default function AdminDashboard() {
  const router = useRouter();
  const [userName, setUserName] = useState("");
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState("");
  const [stats, setStats] = useState<DashboardStats>({
    totalCourses: 0, publishedCourses: 0, draftCourses: 0,
    totalEnrollments: 0, pendingEnrollments: 0,
    totalStudents: 0, totalTeachers: 0, activeStudents: 0,
  });

  useEffect(() => {
    const role = sessionStorage.getItem("lms_selected_role");
    if (role !== "ADMIN") { router.push("/lms"); return; }
    setUserName(getCookie("userName") || "Admin");
    loadDashboard();
  }, []);

  const loadDashboard = useCallback(async () => {
    setLoading(true);
    try {
      // Replace with real API calls
      setStats({
        totalCourses: 12, publishedCourses: 8, draftCourses: 4,
        totalEnrollments: 156, pendingEnrollments: 8,
        totalStudents: 45, totalTeachers: 12, activeStudents: 38,
      });
    } catch { setError("Không thể tải dữ liệu."); }
    finally { setLoading(false); }
  }, []);

  const handleSync = async () => {
    setSyncing(true);
    try {
      const token = getCookie("authToken");
      const res = await fetch("http://localhost:8081/api/v1/admin/sync-users", {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      });
      if (res.ok) {
        const data = await res.json();
        alert(`✅ Đã đồng bộ ${data.synced_count ?? 0} người dùng.`);
        loadDashboard();
      } else {
        const e = await res.json();
        setError(`Đồng bộ thất bại: ${e.error ?? "Unknown error"}`);
      }
    } catch { setError("Lỗi kết nối khi đồng bộ."); }
    finally { setSyncing(false); }
  };

  if (loading) return <PageLoader message="Đang tải dashboard..." />;

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">

        {/* Header */}
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <p className="text-sm text-slate-500 dark:text-slate-500 uppercase tracking-wider font-semibold mb-1">
              Quản trị viên
            </p>
            <h1 className="text-3xl font-extrabold text-slate-900 dark:text-slate-50 leading-tight">
              Dashboard LMS 👑
            </h1>
            <p className="text-slate-600 dark:text-slate-400 mt-1">
              Xin chào, <span className="font-semibold">{userName}</span>. Có {stats.pendingEnrollments} yêu cầu cần xử lý.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <SecondaryBtn
              size="sm"
              icon={<RefreshCw className="w-4 h-4" />}
              onClick={loadDashboard}
            >
              Làm mới
            </SecondaryBtn>
            <GhostBtn size="sm" icon={<Home className="w-4 h-4" />} onClick={() => router.push("/")}>
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

        {error && <Alert type="error">{error}</Alert>}

        {/* Stats row */}
        <div className="grid grid-cols-3 lg:grid-cols-3 gap-4">
          <StatCard
            label="Tổng khóa học"
            value={stats.totalCourses}
            sub={`${stats.publishedCourses} đã xuất bản`}
            icon={<BookOpen className="w-5 h-5" />}
            accent="blue"
          />
          <StatCard
            label="Tổng đăng ký"
            value={stats.totalEnrollments}
            sub={`${stats.pendingEnrollments} chờ duyệt`}
            icon={<CheckCircle2 className="w-5 h-5" />}
            accent={stats.pendingEnrollments > 0 ? "orange" : "green"}
          />
          <StatCard
            label="Học viên"
            value={stats.totalStudents}
            sub={`${stats.activeStudents} đang hoạt động`}
            icon={<Users className="w-5 h-5" />}
            accent="purple"
          />
          <StatCard
            label="Giảng viên"
            value={stats.totalTeachers}
            icon={<Shield className="w-5 h-5" />}
            accent="blue"
          />
        </div>

        {/* Two-column */}
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">

          {/* Quick actions (3/5) */}
          <Card className="lg:col-span-3 p-6">
            <SectionHeader title="Thao tác nhanh" />
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
              <ActionItem
                icon={<RefreshCw className="w-5 h-5" />}
                label="Đồng bộ người dùng"
                description="Sync từ Auth Service"
                onClick={handleSync}
                accent
              />
              <ActionItem
                icon={<Plus className="w-5 h-5" />}
                label="Thêm khóa học"
                description="Tạo khóa học mới"
                onClick={() => router.push("/lms/admin/courses/create")}
              />
              <ActionItem
                icon={<CheckCircle2 className="w-5 h-5" />}
                label="Duyệt đăng ký"
                description="Xử lý yêu cầu"
                badge={stats.pendingEnrollments}
                onClick={() => router.push("/lms/admin/enrollments")}
              />
              <ActionItem
                icon={<BarChart3 className="w-5 h-5" />}
                label="Báo cáo"
                description="Thống kê chi tiết"
                onClick={() => router.push("/lms/admin/analytics")}
              />
              <ActionItem
                icon={<Users className="w-5 h-5" />}
                label="Quản lý người dùng"
                description="Phân quyền & quản lý"
                onClick={() => router.push("/lms/admin/users")}
              />
              <ActionItem
                icon={<Settings className="w-5 h-5" />}
                label="Cài đặt hệ thống"
                description="Cấu hình LMS"
                onClick={() => router.push("/lms/admin/settings")}
              />
            </div>
          </Card>

          {/* System overview (2/5) */}
          <Card className="lg:col-span-2 p-6">
            <SectionHeader title="Tổng quan hệ thống" />
            <div className="space-y-5">
              <ProgressBar
                label="Khóa học đã xuất bản"
                value={stats.publishedCourses}
                max={stats.totalCourses || 1}
                color="blue"
              />
              <ProgressBar
                label="Học viên hoạt động"
                value={stats.activeStudents}
                max={stats.totalStudents || 1}
                color="green"
              />
              <ProgressBar
                label="Đăng ký đã duyệt"
                value={stats.totalEnrollments - stats.pendingEnrollments}
                max={stats.totalEnrollments || 1}
                color="purple"
              />
            </div>

            {/* Mini alert for pending */}
            {stats.pendingEnrollments > 0 && (
              <div className="mt-5 p-3 rounded-xl bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800">
                <div className="flex items-center gap-2">
                  <Clock className="w-4 h-4 text-yellow-600 dark:text-yellow-400 flex-shrink-0" />
                  <p className="text-sm text-yellow-800 dark:text-yellow-300">
                    <span className="font-semibold">{stats.pendingEnrollments}</span> yêu cầu đăng ký đang chờ xử lý
                  </p>
                </div>
              </div>
            )}
          </Card>

        </div>

      </div>
    </div>
  );
}