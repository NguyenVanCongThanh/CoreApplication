package service

import (
	"context"
	"fmt"
	"math"
	"time"

	"example/hello/internal/dto"
	"example/hello/internal/models"
	"example/hello/internal/repository"
	"example/hello/pkg/ai"
)

type FlashcardService struct {
	flashcardRepo *repository.FlashcardRepository
	aiClient      *ai.Client
}

func NewFlashcardService(flashcardRepo *repository.FlashcardRepository, aiClient *ai.Client) *FlashcardService {
	return &FlashcardService{
		flashcardRepo: flashcardRepo,
		aiClient:      aiClient,
	}
}

// GenerateFlashcards calls the AI service to create new flashcards
func (s *FlashcardService) GenerateFlashcards(ctx context.Context, studentID, courseID, nodeID int64, req dto.GenerateFlashcardsRequest) ([]dto.FlashcardResponse, error) {
	// Call AI Service
	aiReq := ai.GenerateFlashcardsRequest{
		StudentID: studentID,
		NodeID:    nodeID,
		CourseID:  courseID,
		Count:     req.Count,
	}

	aiResp, err := s.aiClient.GenerateFlashcards(ctx, aiReq)
	if err != nil {
		return nil, fmt.Errorf("failed to generate flashcards via AI: %w", err)
	}

	var results []dto.FlashcardResponse

	for _, aiFc := range aiResp.Flashcards {
		fc := &models.Flashcard{
			CourseID:  courseID,
			NodeID:    nodeID,
			StudentID: studentID,
			FrontText: aiFc.FrontText,
			BackText:  aiFc.BackText,
			Status:    models.FlashcardStatusActive,
		}

		if err := s.flashcardRepo.CreateFlashcard(ctx, fc); err != nil {
			return nil, fmt.Errorf("failed to save flashcard: %w", err)
		}

		results = append(results, dto.FlashcardResponse{
			ID:        fc.ID,
			CourseID:  fc.CourseID,
			NodeID:    fc.NodeID,
			FrontText: fc.FrontText,
			BackText:  fc.BackText,
			Status:    fc.Status,
			CreatedAt: fc.CreatedAt,
		})
	}

	return results, nil
}

// ListDueFlashcards returns flashcards that are due today or earlier
func (s *FlashcardService) ListDueFlashcards(ctx context.Context, studentID, courseID int64) ([]dto.FlashcardResponse, error) {
	rows, err := s.flashcardRepo.ListDueFlashcards(ctx, studentID, courseID)
	if err != nil {
		return nil, fmt.Errorf("failed to fetch due flashcards: %w", err)
	}

	var results []dto.FlashcardResponse
	for _, r := range rows {
		item := dto.FlashcardResponse{
			ID:        r.ID,
			CourseID:  r.CourseID,
			NodeID:    r.NodeID,
			FrontText: r.FrontText,
			BackText:  r.BackText,
			Status:    r.Status,
			CreatedAt: r.CreatedAt,
		}
		if r.NextReviewDate.Valid {
			v := r.NextReviewDate.Time
			item.NextReviewDate = &v
		}
		if r.SourceDiagnosisID.Valid {
			v := r.SourceDiagnosisID.Int64
			item.SourceDiagnosisID = &v
		}
		results = append(results, item)
	}
	return results, nil
}

// ReviewFlashcard processes a SM-2 quality score (0-5)
func (s *FlashcardService) ReviewFlashcard(ctx context.Context, studentID, flashcardID int64, req dto.ReviewFlashcardRequest) (*dto.ReviewFlashcardResponse, error) {
	rep, err := s.flashcardRepo.GetFlashcardRepetition(ctx, studentID, flashcardID)
	if err != nil {
		return nil, fmt.Errorf("failed to get repetition state: %w", err)
	}
	if rep == nil {
		return nil, fmt.Errorf("repetition state not found")
	}

	// SM-2 Algorithm Calculation
	q := req.Quality
	
	if q >= 3 {
		// Correct response
		if rep.Repetitions == 0 {
			rep.IntervalDays = 1
		} else if rep.Repetitions == 1 {
			rep.IntervalDays = 6
		} else {
			rep.IntervalDays = int(math.Round(float64(rep.IntervalDays) * rep.EasinessFactor))
		}
		rep.Repetitions++
	} else {
		// Incorrect response
		rep.Repetitions = 0
		rep.IntervalDays = 1
	}

	// Update Easiness Factor
	// EF':=EF+(0.1-(5-q)*(0.08+(5-q)*0.02))
	ef := rep.EasinessFactor + (0.1 - float64(5-q)*(0.08+float64(5-q)*0.02))
	if ef < 1.3 {
		ef = 1.3
	}
	rep.EasinessFactor = ef
	rep.QualityLast = q

	// Calculate Next Review Date
	rep.NextReviewDate = time.Now().AddDate(0, 0, rep.IntervalDays)

	if err := s.flashcardRepo.UpdateRepetition(ctx, rep); err != nil {
		return nil, fmt.Errorf("failed to update SM-2 repetition: %w", err)
	}

	return &dto.ReviewFlashcardResponse{
		FlashcardID:    flashcardID,
		EasinessFactor: rep.EasinessFactor,
		IntervalDays:   rep.IntervalDays,
		Repetitions:    rep.Repetitions,
		NextReviewDate: rep.NextReviewDate,
	}, nil
}
