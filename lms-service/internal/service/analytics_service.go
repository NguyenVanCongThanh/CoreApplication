package service

import (
	"context"
	"database/sql"
	"fmt"

	"example/hello/internal/dto"
	"example/hello/internal/repository"
)

type AnalyticsService struct {
	analyticsRepo  *repository.AnalyticsRepository
	courseRepo     *repository.CourseRepository
	enrollmentRepo *repository.EnrollmentRepository
}

func NewAnalyticsService(
	analyticsRepo *repository.AnalyticsRepository,
	courseRepo *repository.CourseRepository,
	enrollmentRepo *repository.EnrollmentRepository,
) *AnalyticsService {
	return &AnalyticsService{
		analyticsRepo:  analyticsRepo,
		courseRepo:     courseRepo,
		enrollmentRepo: enrollmentRepo,
	}
}

// ─── Teacher methods ──────────────────────────────────────────────────────────

func (s *AnalyticsService) GetCourseQuizAnalytics(ctx context.Context, courseID int64) ([]dto.QuizPerformanceSummary, error) {
	rows, err := s.analyticsRepo.GetCourseQuizAnalytics(ctx, courseID)
	if err != nil {
		return nil, fmt.Errorf("GetCourseQuizAnalytics: %w", err)
	}

	result := make([]dto.QuizPerformanceSummary, 0, len(rows))
	for _, r := range rows {
		item := dto.QuizPerformanceSummary{
			QuizID:         r.QuizID,
			QuizTitle:      r.QuizTitle,
			ContentID:      r.ContentID,
			TotalAttempts:  r.TotalAttempts,
			UniqueStudents: r.UniqueStudents,
			AvgScore:       nfv(r.AvgScore),
			AvgPercentage:  nfv(r.AvgPercentage),
			PassRate:       nfv(r.PassRate),
		}
		if r.PassingScore.Valid {
			v := r.PassingScore.Float64
			item.PassingScore = &v
		}
		result = append(result, item)
	}
	return result, nil
}

func (s *AnalyticsService) GetQuizAllAttempts(ctx context.Context, quizID int64) ([]dto.StudentAttemptOverview, error) {
	rows, err := s.analyticsRepo.GetQuizAllAttempts(ctx, quizID)
	if err != nil {
		return nil, fmt.Errorf("GetQuizAllAttempts: %w", err)
	}

	result := make([]dto.StudentAttemptOverview, 0, len(rows))
	for _, r := range rows {
		item := dto.StudentAttemptOverview{
			StudentID:     r.StudentID,
			StudentName:   r.StudentName,
			StudentEmail:  r.StudentEmail,
			QuizID:        r.QuizID,
			QuizTitle:     r.QuizTitle,
			AttemptNumber: r.AttemptNumber,
			TotalPoints:   r.TotalPoints,
			Status:        r.Status,
		}
		if r.EarnedPoints.Valid {
			v := r.EarnedPoints.Float64
			item.EarnedPoints = &v
		}
		if r.Percentage.Valid {
			v := r.Percentage.Float64
			item.Percentage = &v
		}
		if r.IsPassed.Valid {
			v := r.IsPassed.Bool
			item.IsPassed = &v
		}
		if r.SubmittedAt.Valid {
			v := r.SubmittedAt.Time
			item.SubmittedAt = &v
		}
		result = append(result, item)
	}
	return result, nil
}

func (s *AnalyticsService) GetQuizWrongAnswerStats(ctx context.Context, quizID int64) ([]dto.WrongAnswerStat, error) {
	rows, err := s.analyticsRepo.GetQuizWrongAnswerStats(ctx, quizID)
	if err != nil {
		return nil, fmt.Errorf("GetQuizWrongAnswerStats: %w", err)
	}

	result := make([]dto.WrongAnswerStat, 0, len(rows))
	for _, r := range rows {
		result = append(result, dto.WrongAnswerStat{
			QuestionID:   r.QuestionID,
			QuestionText: r.QuestionText,
			QuestionType: r.QuestionType,
			TotalAnswers: r.TotalAnswers,
			WrongCount:   r.WrongCount,
			WrongRate:    r.WrongRate,
		})
	}
	return result, nil
}

func (s *AnalyticsService) GetCourseStudentProgressOverview(ctx context.Context, courseID int64) ([]dto.CourseStudentProgress, error) {
	rows, err := s.analyticsRepo.GetCourseStudentProgressOverview(ctx, courseID)
	if err != nil {
		return nil, fmt.Errorf("GetCourseStudentProgressOverview: %w", err)
	}

	result := make([]dto.CourseStudentProgress, 0, len(rows))
	for _, r := range rows {
		item := dto.CourseStudentProgress{
			StudentID:        r.StudentID,
			StudentName:      r.StudentName,
			StudentEmail:     r.StudentEmail,
			TotalMandatory:   r.TotalMandatory,
			CompletedContent: r.CompletedContent,
			ProgressPercent:  r.ProgressPercent,
		}
		if r.QuizAvgScore.Valid {
			v := r.QuizAvgScore.Float64
			item.QuizAvgScore = &v
		}
		if r.LastActivity.Valid {
			v := r.LastActivity.Time
			item.LastActivity = &v
		}
		result = append(result, item)
	}
	return result, nil
}

// ─── Student method ───────────────────────────────────────────────────────────

func (s *AnalyticsService) GetMyQuizScores(ctx context.Context, courseID, studentID int64) ([]dto.StudentQuizScore, error) {
	rows, err := s.analyticsRepo.GetStudentQuizScores(ctx, courseID, studentID)
	if err != nil {
		return nil, fmt.Errorf("GetMyQuizScores: %w", err)
	}

	result := make([]dto.StudentQuizScore, 0, len(rows))
	for _, r := range rows {
		item := dto.StudentQuizScore{
			QuizID:        r.QuizID,
			QuizTitle:     r.QuizTitle,
			TotalPoints:   r.TotalPoints,
			AttemptsCount: r.AttemptsCount,
			Status:        r.Status,
		}
		if r.BestPct.Valid {
			v := r.BestPct.Float64
			item.BestPercentage = &v
		}
		if r.BestPoints.Valid {
			v := r.BestPoints.Float64
			item.BestPoints = &v
		}
		if r.IsPassed.Valid {
			v := r.IsPassed.Bool
			item.IsPassed = &v
		}
		if r.PassingScore.Valid {
			v := r.PassingScore.Float64
			item.PassingScore = &v
		}
		if r.LastAttemptAt.Valid {
			v := r.LastAttemptAt.Time
			item.LastAttemptAt = &v
		}
		result = append(result, item)
	}
	return result, nil
}

// ─── Permission helpers ───────────────────────────────────────────────────────

// VerifyCourseOwnership checks the caller owns the course or is an admin.
func (s *AnalyticsService) VerifyCourseOwnership(ctx context.Context, courseID, userID int64, userRole string) error {
	if userRole == "ADMIN" {
		return nil
	}
	course, err := s.courseRepo.GetByID(ctx, courseID)
	if err != nil {
		return fmt.Errorf("course not found")
	}
	if course.CreatedBy != userID {
		return fmt.Errorf("permission denied: you don't own this course")
	}
	return nil
}

// VerifyQuizCourseOwnership checks the caller owns the course that contains the quiz.
func (s *AnalyticsService) VerifyQuizCourseOwnership(ctx context.Context, quizID, userID int64, userRole string) error {
	if userRole == "ADMIN" {
		return nil
	}
	courseID, err := s.analyticsRepo.GetQuizCourseID(ctx, quizID)
	if err != nil || courseID == 0 {
		return fmt.Errorf("quiz not found")
	}
	return s.VerifyCourseOwnership(ctx, courseID, userID, userRole)
}

func (s *AnalyticsService) GetCourseStudentWeaknesses(ctx context.Context, courseID, studentID int64) (*dto.StudentWeaknessOverview, error) {
	nodes, err := s.analyticsRepo.GetStudentWeaknesses(ctx, studentID, courseID)
	if err != nil {
		return nil, fmt.Errorf("GetStudentWeaknesses: %w", err)
	}

	var totalWrong, totalAttempt int
	for _, n := range nodes {
		totalWrong += n.WrongCount
		totalAttempt += n.TotalAttempt
	}

	totalWrongPercent := 0.0
	if totalAttempt > 0 {
		totalWrongPercent = float64(totalWrong) / float64(totalAttempt) * 100
	}

	return &dto.StudentWeaknessOverview{
		TotalWrongPercent: totalWrongPercent,
		WeakNodes:         nodes,
	}, nil
}

func (s *AnalyticsService) GetFlashcardStats(ctx context.Context, courseID, studentID int64) (*dto.FlashcardStatsResponse, error) {
	stats, err := s.analyticsRepo.GetFlashcardStats(ctx, studentID, courseID)
	if err != nil {
		return nil, fmt.Errorf("GetFlashcardStats: %w", err)
	}
	return stats, nil
}

// ─── Internal helpers ─────────────────────────────────────────────────────────

// nfv (null float value) returns 0 for invalid NullFloat64.
func nfv(nf sql.NullFloat64) float64 {
	if nf.Valid {
		return nf.Float64
	}
	return 0
}