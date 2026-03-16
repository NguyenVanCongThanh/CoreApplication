package dto

import "time"

// QuizPerformanceSummary aggregates all attempts for one quiz in a course.
// Returned by GET /courses/:courseId/quiz-analytics
type QuizPerformanceSummary struct {
	QuizID         int64    `json:"quiz_id"`
	QuizTitle      string   `json:"quiz_title"`
	ContentID      int64    `json:"content_id"`
	TotalAttempts  int      `json:"total_attempts"`
	UniqueStudents int      `json:"unique_students"`
	AvgScore       float64  `json:"avg_score"`
	AvgPercentage  float64  `json:"avg_percentage"`
	PassRate       float64  `json:"pass_rate"`
	PassingScore   *float64 `json:"passing_score,omitempty"`
}

// StudentAttemptOverview is one row in the all-attempts list.
// Returned by GET /quizzes/:quizId/all-attempts
type StudentAttemptOverview struct {
	StudentID     int64      `json:"student_id"`
	StudentName   string     `json:"student_name"`
	StudentEmail  string     `json:"student_email"`
	QuizID        int64      `json:"quiz_id"`
	QuizTitle     string     `json:"quiz_title"`
	AttemptNumber int        `json:"attempt_number"`
	EarnedPoints  *float64   `json:"earned_points"`
	TotalPoints   float64    `json:"total_points"`
	Percentage    *float64   `json:"percentage"`
	IsPassed      *bool      `json:"is_passed"`
	Status        string     `json:"status"`
	SubmittedAt   *time.Time `json:"submitted_at,omitempty"`
}

// WrongAnswerStat shows how often a question was answered incorrectly.
// Returned by GET /quizzes/:quizId/wrong-answer-stats
type WrongAnswerStat struct {
	QuestionID   int64   `json:"question_id"`
	QuestionText string  `json:"question_text"`
	QuestionType string  `json:"question_type"`
	TotalAnswers int     `json:"total_answers"`
	WrongCount   int     `json:"wrong_count"`
	WrongRate    float64 `json:"wrong_rate"` // 0–100 %
}

// CourseStudentProgress is one enrolled student's overall progress.
// Returned by GET /courses/:courseId/student-progress-overview
type CourseStudentProgress struct {
	StudentID        int64      `json:"student_id"`
	StudentName      string     `json:"student_name"`
	StudentEmail     string     `json:"student_email"`
	CompletedContent int        `json:"completed_content"`
	TotalMandatory   int        `json:"total_mandatory"`
	ProgressPercent  float64    `json:"progress_percent"`
	QuizAvgScore     *float64   `json:"quiz_avg_score,omitempty"`
	LastActivity     *time.Time `json:"last_activity,omitempty"`
}

// StudentQuizScore is the best-attempt summary per quiz for one student.
// Returned by GET /courses/:courseId/my-quiz-scores
// Status: not_started | in_progress | submitted | passed | failed
type StudentQuizScore struct {
	QuizID         int64      `json:"quiz_id"`
	QuizTitle      string     `json:"quiz_title"`
	BestPercentage *float64   `json:"best_percentage"`
	BestPoints     *float64   `json:"best_points"`
	TotalPoints    float64    `json:"total_points"`
	AttemptsCount  int        `json:"attempts_count"`
	IsPassed       *bool      `json:"is_passed"`
	PassingScore   *float64   `json:"passing_score,omitempty"`
	LastAttemptAt  *time.Time `json:"last_attempt_at,omitempty"`
	Status         string     `json:"status"`
}