package service

import (
	"context"
	"fmt"
	"time"

	"example/hello/internal/dto"
	"example/hello/internal/repository"
	"example/hello/pkg/ai"
)

type FlashcardService struct {
	flashcardRepo *repository.FlashcardRepository // Kept for compilation compatibility, but unused
	aiClient      *ai.Client
}

func NewFlashcardService(flashcardRepo *repository.FlashcardRepository, aiClient *ai.Client) *FlashcardService {
	return &FlashcardService{
		flashcardRepo: flashcardRepo,
		aiClient:      aiClient,
	}
}

// GenerateFlashcards calls the AI service to create new flashcards (AI service now persists them)
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
		parsedTime := time.Now()
		if t, err := time.Parse("2006-01-02T15:04:05.999999", aiFc.CreatedAt); err == nil {
			parsedTime = t
		} else if t, err := time.Parse(time.RFC3339, aiFc.CreatedAt); err == nil {
			parsedTime = t
		} else if t, err := time.Parse("2006-01-02T15:04:05", aiFc.CreatedAt); err == nil {
			parsedTime = t
		}

		results = append(results, dto.FlashcardResponse{
			ID:        aiFc.ID,
			CourseID:  aiFc.CourseID,
			NodeID:    aiFc.NodeID,
			FrontText: aiFc.FrontText,
			BackText:  aiFc.BackText,
			Status:    "ACTIVE",
			CreatedAt: parsedTime,
		})
	}

	return results, nil
}

// ListDueFlashcards calls AI service to get flashcards due today
func (s *FlashcardService) ListDueFlashcards(ctx context.Context, studentID, courseID int64) ([]dto.FlashcardResponse, error) {
	rows, err := s.aiClient.GetDueFlashcards(ctx, studentID, courseID)
	if err != nil {
		return nil, fmt.Errorf("failed to fetch due flashcards from AI: %w", err)
	}

	return s.mapAIResultToDTO(rows), nil
}

// ReviewFlashcard processes a SM-2 quality score (0-5) via AI service
func (s *FlashcardService) ReviewFlashcard(ctx context.Context, studentID, flashcardID int64, req dto.ReviewFlashcardRequest) (*dto.ReviewFlashcardResponse, error) {
	aiReq := ai.ReviewFlashcardRequest{
		StudentID:   studentID,
		FlashcardID: flashcardID,
		Quality:     req.Quality,
	}
	resp, err := s.aiClient.ReviewFlashcard(ctx, aiReq)
	if err != nil {
		return nil, fmt.Errorf("failed to review flashcard via AI: %w", err)
	}

	result := &dto.ReviewFlashcardResponse{
		FlashcardID: flashcardID,
	}

	if v, ok := resp["easiness_factor"].(float64); ok {
		result.EasinessFactor = v
	}
	if v, ok := resp["interval_days"].(float64); ok {
		result.IntervalDays = int(v)
	}
	if v, ok := resp["repetitions"].(float64); ok {
		result.Repetitions = int(v)
	}
	if v, ok := resp["next_review_date"].(string); ok {
		if t, err := time.Parse(time.RFC3339, v); err == nil {
			result.NextReviewDate = t
		}
	}

	return result, nil
}

// ListFlashcardsByNode returns ALL flashcards for a student+course+node via AI
func (s *FlashcardService) ListFlashcardsByNode(ctx context.Context, studentID, courseID, nodeID int64) ([]dto.FlashcardResponse, error) {
	rows, err := s.aiClient.GetNodeFlashcards(ctx, nodeID, courseID, studentID)
	if err != nil {
		return nil, fmt.Errorf("failed to fetch node flashcards from AI: %w", err)
	}

	return s.mapAIResultToDTO(rows), nil
}

// Helper to map map[string]interface{} rows to dto.FlashcardResponse
func (s *FlashcardService) mapAIResultToDTO(rows []map[string]interface{}) []dto.FlashcardResponse {
	var results []dto.FlashcardResponse
	for _, r := range rows {
		item := dto.FlashcardResponse{}
		
		if v, ok := r["id"].(float64); ok {
			item.ID = int64(v)
		}
		if v, ok := r["course_id"].(float64); ok {
			item.CourseID = int64(v)
		}
		if v, ok := r["node_id"].(float64); ok {
			item.NodeID = int64(v)
		}
		if v, ok := r["front_text"].(string); ok {
			item.FrontText = v
		}
		if v, ok := r["back_text"].(string); ok {
			item.BackText = v
		}
		if v, ok := r["status"].(string); ok {
			item.Status = v
		}
		if v, ok := r["created_at"].(string); ok {
			if t, err := time.Parse("2006-01-02T15:04:05.999999", v); err == nil {
				item.CreatedAt = t
			} else if t, err := time.Parse(time.RFC3339, v); err == nil {
				item.CreatedAt = t
			} else if t, err := time.Parse("2006-01-02T15:04:05", v); err == nil {
				item.CreatedAt = t
			}
		}
		if v, ok := r["next_review_date"].(string); ok {
			if t, err := time.Parse("2006-01-02", v); err == nil {
				item.NextReviewDate = &t
			}
		}
		if v, ok := r["easiness_factor"].(float64); ok {
			item.EasinessFactor = &v
		}
		if v, ok := r["interval_days"].(float64); ok {
			val := int(v)
			item.IntervalDays = &val
		}
		if v, ok := r["repetitions"].(float64); ok {
			val := int(v)
			item.Repetitions = &val
		}
		if v, ok := r["last_reviewed_at"].(string); ok {
			if t, err := time.Parse(time.RFC3339, v); err == nil {
				item.LastReviewedAt = &t
			}
		}

		results = append(results, item)
	}
	return results
}
