package dto

import "time"

// Flashcards

// GenerateFlashcardsRequest represents requesting AI to generate flashcards for a specific weak node
type GenerateFlashcardsRequest struct {
	Count int `json:"count" binding:"omitempty,min=1,max=20"`
}

// FlashcardResponse represents a single flashcard
type FlashcardResponse struct {
	ID                int64      `json:"id"`
	CourseID          int64      `json:"course_id"`
	NodeID            int64      `json:"node_id"`
	FrontText         string     `json:"front_text"`
	BackText          string     `json:"back_text"`
	SourceDiagnosisID *int64     `json:"source_diagnosis_id,omitempty"`
	Status            string     `json:"status"`
	NextReviewDate    *time.Time `json:"next_review_date,omitempty"` // from repetition
	CreatedAt         time.Time  `json:"created_at"`
}

// ReviewFlashcardRequest represents the student's self-assessed quality of recalling the flashcard
type ReviewFlashcardRequest struct {
	Quality int `json:"quality" binding:"required,min=0,max=5"`
	// 0: Complete blackout
	// 1: Incorrect, but remembered the correct one upon seeing it
	// 2: Incorrect, where the correct one seemed easy to recall
	// 3: Correct, but required significant effort
	// 4: Correct, after hesitation
	// 5: Correct, perfect response
}

// ReviewFlashcardResponse returns the updated SM-2 stats
type ReviewFlashcardResponse struct {
	FlashcardID    int64      `json:"flashcard_id"`
	EasinessFactor float64    `json:"easiness_factor"`
	IntervalDays   int        `json:"interval_days"`
	Repetitions    int        `json:"repetitions"`
	NextReviewDate time.Time  `json:"next_review_date"`
}
