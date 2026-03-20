-- ============================================================
-- Migration 012: Auto-Accept Enrollment
-- Sinh viên đăng ký khóa học được vào học ngay,
-- không cần chờ giáo viên duyệt.
-- ============================================================

-- ============================================================
-- STEP 1: Backfill — Accept toàn bộ enrollment đang WAITING
-- ============================================================
UPDATE enrollments
SET
    status      = 'ACCEPTED',
    accepted_at = CURRENT_TIMESTAMP,
    updated_at  = CURRENT_TIMESTAMP
WHERE status = 'WAITING';

-- ============================================================
-- STEP 2: Đổi default status của enrollment mới thành ACCEPTED
-- ============================================================
ALTER TABLE enrollments
    ALTER COLUMN status SET DEFAULT 'ACCEPTED';

-- ============================================================
-- STEP 3: Trigger — Tự động accept ngay khi INSERT enrollment mới
-- Đảm bảo mọi enrollment dù được tạo từ đâu (API, batch, etc.)
-- đều luôn có status = ACCEPTED và accepted_at được set.
-- ============================================================
CREATE OR REPLACE FUNCTION auto_accept_enrollment()
RETURNS TRIGGER AS $$
BEGIN
    NEW.status      := 'ACCEPTED';
    NEW.accepted_at := CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_auto_accept_enrollment
    BEFORE INSERT ON enrollments
    FOR EACH ROW
    EXECUTE FUNCTION auto_accept_enrollment();

-- ============================================================
-- VERIFICATION — Chạy để kiểm tra kết quả sau migration
-- ============================================================
-- SELECT status, COUNT(*) FROM enrollments GROUP BY status;
-- Kết quả mong đợi: chỉ còn ACCEPTED (và REJECTED nếu có)