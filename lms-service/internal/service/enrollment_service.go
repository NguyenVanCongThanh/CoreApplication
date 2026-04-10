package service

import (
	"context"
	"database/sql"
	"fmt"
	"time"

	"example/hello/internal/dto"
	"example/hello/internal/models"
	"example/hello/internal/repository"
)

type EnrollmentService struct {
	enrollmentRepo *repository.EnrollmentRepository
	courseRepo     *repository.CourseRepository
	userRepo       *repository.UserRepository
	progressRepo   *repository.ProgressRepository
}

func NewEnrollmentService(
	enrollmentRepo *repository.EnrollmentRepository,
	courseRepo *repository.CourseRepository,
	userRepo *repository.UserRepository,
	progressRepo *repository.ProgressRepository,
) *EnrollmentService {
	return &EnrollmentService{
		enrollmentRepo: enrollmentRepo,
		courseRepo:     courseRepo,
		userRepo:       userRepo,
		progressRepo:   progressRepo,
	}
}

// EnrollCourse enrolls a student in a course
func (s *EnrollmentService) EnrollCourse(ctx context.Context, courseID, studentID int64) (*dto.EnrollmentResponse, error) {
	// Check if course exists
	_, err := s.courseRepo.GetByID(ctx, courseID)
	if err != nil {
		return nil, fmt.Errorf("course not found")
	}

	// Check if already enrolled
	existing, _ := s.enrollmentRepo.GetByStudentAndCourse(ctx, studentID, courseID)
	if existing != nil {
		return nil, fmt.Errorf("student already enrolled in this course")
	}

	// Create enrollment with WAITING status
	enrollment := &models.Enrollment{
		CourseID:  courseID,
		StudentID: studentID,
		Status:    models.EnrollmentAccepted,
	}

	result, err := s.enrollmentRepo.Create(ctx, enrollment)
	if err != nil {
		return nil, err
	}

	return toEnrollmentResponse(result), nil
}

// GetMyEnrollments gets all enrollments for a student
func (s *EnrollmentService) GetMyEnrollments(ctx context.Context, studentID int64, status string) ([]*dto.StudentEnrollmentResponse, error) {
	enrollments, err := s.enrollmentRepo.ListByStudent(ctx, studentID, status)
	if err != nil {
		return nil, err
	}

	var responses []*dto.StudentEnrollmentResponse
	for _, e := range enrollments {
		var progress float64 = 0
		if s.progressRepo != nil {
			progressResult, err := s.progressRepo.GetCourseProgress(ctx, e.CourseID, studentID)
			if err == nil && progressResult != nil {
				progress = progressResult.ProgressPercent
			}
		}
		
		responses = append(responses, &dto.StudentEnrollmentResponse{
			ID:          e.ID,
			CourseID:    e.CourseID,
			CourseTitle: e.CourseTitle,
			Status:      e.Status,
			TeacherName: e.TeacherName,
			EnrolledAt:  e.EnrolledAt,
			AcceptedAt:  extractTime(e.AcceptedAt),
			ProgressPercent: progress,
		})
	}

	return responses, nil
}

// GetCourseLearners gets all learners in a course
func (s *EnrollmentService) GetCourseLearners(ctx context.Context, courseID int64, status string, userID int64, role string) ([]*dto.LearnerResponse, error) {
	// Check if user is course creator (teacher)
	course, err := s.courseRepo.GetByID(ctx, courseID)
	if err != nil {
		return nil, fmt.Errorf("course not found")
	}

	if course.CreatedBy != userID && role != "ADMIN" {
		return nil, fmt.Errorf("unauthorized: only course creator can view learners")
	}

	enrollments, err := s.enrollmentRepo.ListByCourse(ctx, courseID, status)
	if err != nil {
		return nil, err
	}

	var responses []*dto.LearnerResponse
	for _, e := range enrollments {
		responses = append(responses, &dto.LearnerResponse{
			ID:          e.ID,
			CourseID:    e.CourseID,
			StudentID:   e.StudentID,
			StudentName: e.StudentName,
			Email:       e.StudentEmail,
			Status:      e.Status,
			EnrolledAt:  e.EnrolledAt,
			AcceptedAt:  extractTime(e.AcceptedAt),
		})
	}

	return responses, nil
}

// AcceptEnrollment accepts an enrollment request
func (s *EnrollmentService) AcceptEnrollment(ctx context.Context, enrollmentID, courseID int64, userID int64, role string) error {
	// Verify user is course creator
	course, err := s.courseRepo.GetByID(ctx, courseID)
	if err != nil {
		return fmt.Errorf("course not found")
	}

	if course.CreatedBy != userID && role != "ADMIN" {
		return fmt.Errorf("unauthorized")
	}

	return s.enrollmentRepo.UpdateStatus(ctx, enrollmentID, models.EnrollmentAccepted)
}

// RejectEnrollment rejects an enrollment request
func (s *EnrollmentService) RejectEnrollment(ctx context.Context, enrollmentID, courseID int64, userID int64, role string) error {
	// Verify user is course creator
	course, err := s.courseRepo.GetByID(ctx, courseID)
	if err != nil {
		return fmt.Errorf("course not found")
	}

	if course.CreatedBy != userID && role != "ADMIN" {
		return fmt.Errorf("unauthorized")
	}

	return s.enrollmentRepo.UpdateStatus(ctx, enrollmentID, models.EnrollmentRejected)
}

// BulkEnroll enrolls multiple students in a course
func (s *EnrollmentService) BulkEnroll(
	ctx context.Context,
	courseID int64,
	studentIDs []int64,
	teacherID int64,
	role string,
) *dto.BulkEnrollmentResponse {
	total := len(studentIDs)
 
	// 1. Kiểm tra quyền — 1 query
	course, err := s.courseRepo.GetByID(ctx, courseID)
	if err != nil || (course.CreatedBy != teacherID && role != "ADMIN") {
		return &dto.BulkEnrollmentResponse{
			TotalCount: total,
			Succeeded:  []int64{},
			Failed:     []dto.EnrollmentError{{StudentID: 0, Error: "unauthorized or course not found"}},
		}
	}
 
	// 2. Batch INSERT — 1 query, bỏ qua duplicate qua ON CONFLICT
	inserted, err := s.enrollmentRepo.BulkCreate(ctx, courseID, studentIDs)
	if err != nil {
		// Toàn bộ batch fail — trả về lỗi cho tất cả
		failed := make([]dto.EnrollmentError, total)
		for i, sid := range studentIDs {
			failed[i] = dto.EnrollmentError{StudentID: sid, Error: err.Error()}
		}
		return &dto.BulkEnrollmentResponse{
			TotalCount: total,
			Succeeded:  []int64{},
			Failed:     failed,
		}
	}
 
	// 3. Xác định ai bị skip (đã enrolled) — O(N) với map lookup
	insertedSet := make(map[int64]struct{}, len(inserted))
	for _, sid := range inserted {
		insertedSet[sid] = struct{}{}
	}
 
	failed := make([]dto.EnrollmentError, 0, total-len(inserted))
	for _, sid := range studentIDs {
		if _, ok := insertedSet[sid]; !ok {
			failed = append(failed, dto.EnrollmentError{
				StudentID: sid,
				Error:     "already enrolled",
			})
		}
	}
 
	return &dto.BulkEnrollmentResponse{
		TotalCount: total,
		Succeeded:  inserted,
		Failed:     failed,
	}
}

// CancelEnrollment allows student to cancel their enrollment
func (s *EnrollmentService) CancelEnrollment(ctx context.Context, enrollmentID int64, studentID int64) error {
	enrollment, err := s.enrollmentRepo.GetByID(ctx, enrollmentID)
	if err != nil {
		return fmt.Errorf("enrollment not found")
	}

	if enrollment.StudentID != studentID {
		return fmt.Errorf("unauthorized")
	}

	return s.enrollmentRepo.Delete(ctx, enrollmentID)
}

// VerifyAccess checks if a user has access to a course (enrolled via ACCEPTED status, or is creator, or is ADMIN)
func (s *EnrollmentService) VerifyAccess(ctx context.Context, userID, courseID int64, role string) error {
	// Admin bypass
	if role == "ADMIN" {
		return nil
	}

	// First check if they are the course creator
	course, err := s.courseRepo.GetByID(ctx, courseID)
	if err != nil {
		return fmt.Errorf("course not found: %w", err)
	}
	if course.CreatedBy == userID {
		return nil
	}
	
	// Check if enrolled and ACCEPTED
	enrollment, err := s.enrollmentRepo.GetByStudentAndCourse(ctx, userID, courseID)
	if err != nil {
		return fmt.Errorf("student not enrolled")
	}
	if enrollment.Status != models.EnrollmentAccepted {
		return fmt.Errorf("enrollment is %s, not ACCEPTED", enrollment.Status)
	}

	return nil
}

// Helper functions

func toEnrollmentResponse(e *models.Enrollment) *dto.EnrollmentResponse {
	return &dto.EnrollmentResponse{
		ID:         e.ID,
		CourseID:   e.CourseID,
		StudentID:  e.StudentID,
		Status:     e.Status,
		EnrolledAt: e.EnrolledAt,
		AcceptedAt: extractTime(e.AcceptedAt),
		RejectedAt: extractTime(e.RejectedAt),
		CreatedAt:  e.CreatedAt,
		UpdatedAt:  e.UpdatedAt,
	}
}

func extractTime(t sql.NullTime) *time.Time {
	if t.Valid {
		return &t.Time
	}
	return nil
}
