package service

import (
	"context"
	"fmt"

	"example/hello/internal/dto"
	"example/hello/internal/repository"
)

type ProgressService struct {
	progressRepo   *repository.ProgressRepository
	enrollmentRepo *repository.EnrollmentRepository
}

func NewProgressService(
	progressRepo *repository.ProgressRepository,
	enrollmentRepo *repository.EnrollmentRepository,
) *ProgressService {
	return &ProgressService{
		progressRepo:   progressRepo,
		enrollmentRepo: enrollmentRepo,
	}
}

// MarkContentComplete marks a mandatory content item as completed for a student.
//
// Rules:
//   - The student must have ACCEPTED enrollment in the course that owns the content.
//   - Non-mandatory items are silently accepted without writing to the DB.
//   - Duplicate calls are idempotent.
func (s *ProgressService) MarkContentComplete(ctx context.Context, contentID, studentID int64) error {
	// 1. Resolve course
	courseID, err := s.progressRepo.GetContentCourseID(ctx, contentID)
	if err != nil {
		return fmt.Errorf("failed to resolve content: %w", err)
	}
	if courseID == 0 {
		return fmt.Errorf("content not found")
	}

	// 2. Verify enrollment
	enrollment, err := s.enrollmentRepo.GetByStudentAndCourse(ctx, studentID, courseID)
	if err != nil || enrollment == nil {
		return fmt.Errorf("student is not enrolled in this course")
	}
	if enrollment.Status != "ACCEPTED" {
		return fmt.Errorf("enrollment is not accepted")
	}

	// 3. Check mandatory flag — non-mandatory: no-op
	mandatory, err := s.progressRepo.GetContentIsMandatory(ctx, contentID)
	if err != nil {
		return fmt.Errorf("failed to check content: %w", err)
	}
	if !mandatory {
		return nil
	}

	// 4. Persist (idempotent)
	return s.progressRepo.MarkComplete(ctx, contentID, studentID)
}

// GetMyCourseProgress returns a summary of mandatory-content completion.
func (s *ProgressService) GetMyCourseProgress(ctx context.Context, courseID, studentID int64) (*dto.CourseProgressResponse, error) {
	result, err := s.progressRepo.GetCourseProgress(ctx, courseID, studentID)
	if err != nil {
		return nil, fmt.Errorf("failed to get progress: %w", err)
	}

	ids := result.CompletedContentIDs
	if ids == nil {
		ids = []int64{}
	}

	return &dto.CourseProgressResponse{
		CourseID:            courseID,
		TotalMandatory:      result.TotalMandatory,
		CompletedCount:      result.CompletedCount,
		ProgressPercent:     result.ProgressPercent,
		CompletedContentIDs: ids,
	}, nil
}

// GetMyCourseProgressDetail returns per-item completion status.
func (s *ProgressService) GetMyCourseProgressDetail(ctx context.Context, courseID, studentID int64) (*dto.CourseProgressDetailResponse, error) {
	summary, err := s.GetMyCourseProgress(ctx, courseID, studentID)
	if err != nil {
		return nil, err
	}

	rows, err := s.progressRepo.GetCourseProgressDetail(ctx, courseID, studentID)
	if err != nil {
		return nil, fmt.Errorf("failed to get progress detail: %w", err)
	}

	items := make([]dto.ProgressDetailItem, 0, len(rows))
	for _, row := range rows {
		items = append(items, dto.ProgressDetailItem{
			ContentID:    row.ContentID,
			ContentTitle: row.ContentTitle,
			ContentType:  row.ContentType,
			SectionTitle: row.SectionTitle,
			IsMandatory:  row.IsMandatory,
			IsCompleted:  row.IsCompleted,
			CompletedAt:  row.CompletedAt,
		})
	}

	return &dto.CourseProgressDetailResponse{
		CourseID: courseID,
		Summary:  *summary,
		Items:    items,
	}, nil
}