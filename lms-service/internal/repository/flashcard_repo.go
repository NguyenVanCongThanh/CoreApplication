package repository

import (
	"context"
	"database/sql"
	"fmt"

	"example/hello/internal/models"
)

type FlashcardRepository struct {
	db *sql.DB
}

func NewFlashcardRepository(db *sql.DB) *FlashcardRepository {
	return &FlashcardRepository{db: db}
}

// CreateFlashcard creates a new flashcard and initializes its repetition state
func (r *FlashcardRepository) CreateFlashcard(ctx context.Context, f *models.Flashcard) error {
	tx, err := r.db.BeginTx(ctx, nil)
	if err != nil {
		return err
	}
	defer tx.Rollback()

	query := `
		INSERT INTO flashcards (
			course_id, node_id, student_id, front_text, back_text, source_diagnosis_id, status
		) VALUES ($1, $2, $3, $4, $5, $6, $7)
		RETURNING id, created_at, updated_at
	`
	err = tx.QueryRowContext(
		ctx, query,
		f.CourseID, f.NodeID, f.StudentID, f.FrontText, f.BackText, f.SourceDiagnosisID, f.Status,
	).Scan(&f.ID, &f.CreatedAt, &f.UpdatedAt)
	if err != nil {
		return err
	}

	// Initialize SM-2 repetition state
	repQuery := `
		INSERT INTO flashcard_repetitions (
			student_id, flashcard_id, course_id, easiness_factor, interval_days, repetitions, quality_last, next_review_date
		) VALUES ($1, $2, $3, 2.5, 1, 0, 0, CURRENT_DATE)
	`
	_, err = tx.ExecContext(ctx, repQuery, f.StudentID, f.ID, f.CourseID)
	if err != nil {
		return err
	}

	return tx.Commit()
}

// ListDueFlashcards returns flashcards joined with their repetition data that are due for review today or earlier.
func (r *FlashcardRepository) ListDueFlashcards(ctx context.Context, studentID, courseID int64) ([]models.FlashcardWithRepetition, error) {
	query := `
		SELECT 
			f.id, f.course_id, f.node_id, f.student_id, f.front_text, f.back_text, f.source_diagnosis_id, f.status, f.created_at, f.updated_at,
			fr.id as repetition_id, fr.easiness_factor, fr.interval_days, fr.repetitions, fr.quality_last, fr.next_review_date, fr.last_reviewed_at
		FROM flashcards f
		JOIN flashcard_repetitions fr ON fr.flashcard_id = f.id
		WHERE f.student_id = $1 AND f.course_id = $2
		  AND f.status = 'ACTIVE'
		  AND fr.next_review_date <= CURRENT_DATE
		ORDER BY fr.next_review_date ASC, f.created_at ASC
	`
	rows, err := r.db.QueryContext(ctx, query, studentID, courseID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var result []models.FlashcardWithRepetition
	for rows.Next() {
		var item models.FlashcardWithRepetition
		err := rows.Scan(
			&item.ID, &item.CourseID, &item.NodeID, &item.StudentID, &item.FrontText, &item.BackText, &item.SourceDiagnosisID, &item.Status, &item.CreatedAt, &item.UpdatedAt,
			&item.RepetitionID, &item.EasinessFactor, &item.IntervalDays, &item.Repetitions, &item.QualityLast, &item.NextReviewDate, &item.LastReviewedAt,
		)
		if err != nil {
			return nil, err
		}
		result = append(result, item)
	}
	return result, rows.Err()
}

// GetFlashcardRepetition fetches the repetition row for a given flashcard
func (r *FlashcardRepository) GetFlashcardRepetition(ctx context.Context, studentID, flashcardID int64) (*models.FlashcardRepetition, error) {
	var rep models.FlashcardRepetition
	query := `
		SELECT 
			id, student_id, flashcard_id, course_id, easiness_factor, interval_days, repetitions, quality_last, next_review_date, last_reviewed_at, created_at, updated_at
		FROM flashcard_repetitions
		WHERE student_id = $1 AND flashcard_id = $2
	`
	err := r.db.QueryRowContext(ctx, query, studentID, flashcardID).Scan(
		&rep.ID, &rep.StudentID, &rep.FlashcardID, &rep.CourseID, &rep.EasinessFactor, &rep.IntervalDays, &rep.Repetitions, &rep.QualityLast, &rep.NextReviewDate, &rep.LastReviewedAt, &rep.CreatedAt, &rep.UpdatedAt,
	)
	if err != nil {
		if err == sql.ErrNoRows {
			return nil, nil // Return nil if explicitly not found
		}
		return nil, err
	}
	return &rep, nil
}

// UpdateRepetition updates the SM-2 state of a flashcard
func (r *FlashcardRepository) UpdateRepetition(ctx context.Context, rep *models.FlashcardRepetition) error {
	query := `
		UPDATE flashcard_repetitions SET
			easiness_factor = $1,
			interval_days = $2,
			repetitions = $3,
			quality_last = $4,
			next_review_date = $5,
			last_reviewed_at = CURRENT_TIMESTAMP,
			updated_at = CURRENT_TIMESTAMP
		WHERE id = $6 AND student_id = $7
		RETURNING updated_at
	`
	return r.db.QueryRowContext(ctx, query,
		rep.EasinessFactor, rep.IntervalDays, rep.Repetitions, rep.QualityLast, rep.NextReviewDate,
		rep.ID, rep.StudentID,
	).Scan(&rep.UpdatedAt)
}

// ListFlashcardsByNode returns ALL flashcards for a student+course+node regardless of status or due date.
// Joined with flashcard_repetitions to include SM-2 state for display purposes.
func (r *FlashcardRepository) ListFlashcardsByNode(ctx context.Context, studentID, courseID, nodeID int64) ([]models.FlashcardWithRepetition, error) {
	query := `
		SELECT
			f.id, f.course_id, f.node_id, f.student_id, f.front_text, f.back_text, f.source_diagnosis_id, f.status, f.created_at, f.updated_at,
			fr.id AS repetition_id, fr.easiness_factor, fr.interval_days, fr.repetitions, fr.quality_last, fr.next_review_date, fr.last_reviewed_at
		FROM flashcards f
		LEFT JOIN flashcard_repetitions fr ON fr.flashcard_id = f.id AND fr.student_id = f.student_id
		WHERE f.student_id = $1 AND f.course_id = $2 AND f.node_id = $3
		ORDER BY f.created_at DESC
	`
	rows, err := r.db.QueryContext(ctx, query, studentID, courseID, nodeID)
	if err != nil {
		return nil, fmt.Errorf("FlashcardRepo.ListFlashcardsByNode: %w", err)
	}
	defer rows.Close()

	var result []models.FlashcardWithRepetition
	for rows.Next() {
		var item models.FlashcardWithRepetition
		if err := rows.Scan(
			&item.ID, &item.CourseID, &item.NodeID, &item.StudentID, &item.FrontText, &item.BackText, &item.SourceDiagnosisID, &item.Status, &item.CreatedAt, &item.UpdatedAt,
			&item.RepetitionID, &item.EasinessFactor, &item.IntervalDays, &item.Repetitions, &item.QualityLast, &item.NextReviewDate, &item.LastReviewedAt,
		); err != nil {
			return nil, fmt.Errorf("FlashcardRepo.ListFlashcardsByNode scan: %w", err)
		}
		result = append(result, item)
	}
	return result, rows.Err()
}
