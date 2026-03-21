package models

import (
	"database/sql"
	"time"
)

// Flashcard Status Constants
const (
	FlashcardStatusActive   = "ACTIVE"
	FlashcardStatusInactive = "INACTIVE"
	FlashcardStatusArchived = "ARCHIVED"
)

// Flashcard represents an AI-generated flashcard
type Flashcard struct {
	ID                int64          `json:"id" db:"id"`
	CourseID          int64          `json:"course_id" db:"course_id"`
	NodeID            int64          `json:"node_id" db:"node_id"`
	StudentID         int64          `json:"student_id" db:"student_id"`
	FrontText         string         `json:"front_text" db:"front_text"`
	BackText          string         `json:"back_text" db:"back_text"`
	SourceDiagnosisID sql.NullInt64  `json:"source_diagnosis_id" db:"source_diagnosis_id"`
	Status            string         `json:"status" db:"status"`
	CreatedAt         time.Time      `json:"created_at" db:"created_at"`
	UpdatedAt         time.Time      `json:"updated_at" db:"updated_at"`
}

// FlashcardRepetition tracks the SM-2 algorithm state for a flashcard
type FlashcardRepetition struct {
	ID             int64        `json:"id" db:"id"`
	StudentID      int64        `json:"student_id" db:"student_id"`
	FlashcardID    int64        `json:"flashcard_id" db:"flashcard_id"`
	CourseID       int64        `json:"course_id" db:"course_id"`
	EasinessFactor float64      `json:"easiness_factor" db:"easiness_factor"`
	IntervalDays   int          `json:"interval_days" db:"interval_days"`
	Repetitions    int          `json:"repetitions" db:"repetitions"`
	QualityLast    int          `json:"quality_last" db:"quality_last"`
	NextReviewDate time.Time    `json:"next_review_date" db:"next_review_date"` // Stored as DATE, mapped to Time
	LastReviewedAt sql.NullTime `json:"last_reviewed_at" db:"last_reviewed_at"`
	CreatedAt      time.Time    `json:"created_at" db:"created_at"`
	UpdatedAt      time.Time    `json:"updated_at" db:"updated_at"`
}

// FlashcardWithRepetition is a joined model for reviewing
type FlashcardWithRepetition struct {
	Flashcard
	RepetitionID   sql.NullInt64   `json:"repetition_id" db:"repetition_id"`
	EasinessFactor sql.NullFloat64 `json:"easiness_factor" db:"easiness_factor"`
	IntervalDays   sql.NullInt32   `json:"interval_days" db:"interval_days"`
	Repetitions    sql.NullInt32   `json:"repetitions" db:"repetitions"`
	QualityLast    sql.NullInt32   `json:"quality_last" db:"quality_last"`
	NextReviewDate sql.NullTime    `json:"next_review_date" db:"next_review_date"`
	LastReviewedAt sql.NullTime    `json:"last_reviewed_at" db:"last_reviewed_at"`
}
