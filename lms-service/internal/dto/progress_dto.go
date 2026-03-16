package dto

import "time"

// CourseProgressResponse is returned by GET /courses/:courseId/my-progress
type CourseProgressResponse struct {
	CourseID            int64   `json:"course_id"`
	TotalMandatory      int     `json:"total_mandatory"`
	CompletedCount      int     `json:"completed_count"`
	ProgressPercent     float64 `json:"progress_percent"`
	CompletedContentIDs []int64 `json:"completed_content_ids"`
}

// ProgressDetailItem is one content row with completion status
type ProgressDetailItem struct {
	ContentID    int64      `json:"content_id"`
	ContentTitle string     `json:"content_title"`
	ContentType  string     `json:"content_type"`
	SectionTitle string     `json:"section_title"`
	IsMandatory  bool       `json:"is_mandatory"`
	IsCompleted  bool       `json:"is_completed"`
	CompletedAt  *time.Time `json:"completed_at,omitempty"`
}

// CourseProgressDetailResponse is returned by GET /courses/:courseId/progress-detail
type CourseProgressDetailResponse struct {
	CourseID int64                  `json:"course_id"`
	Summary  CourseProgressResponse `json:"summary"`
	Items    []ProgressDetailItem   `json:"items"`
}