package handler

import (
	"net/http"
	"strconv"

	"example/hello/internal/dto"
	"example/hello/internal/service"

	"github.com/gin-gonic/gin"
)

type AnalyticsHandler struct {
	analyticsService *service.AnalyticsService
}

func NewAnalyticsHandler(analyticsService *service.AnalyticsService) *AnalyticsHandler {
	return &AnalyticsHandler{analyticsService: analyticsService}
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

func getCourseIDParam(c *gin.Context) (int64, bool) {
	id, err := strconv.ParseInt(c.Param("courseId"), 10, 64)
	if err != nil {
		c.JSON(http.StatusBadRequest, dto.NewErrorResponse("invalid_course_id", "Invalid course ID"))
		return 0, false
	}
	return id, true
}

func getQuizIDParam(c *gin.Context) (int64, bool) {
	id, err := strconv.ParseInt(c.Param("quizId"), 10, 64)
	if err != nil {
		c.JSON(http.StatusBadRequest, dto.NewErrorResponse("invalid_quiz_id", "Invalid quiz ID"))
		return 0, false
	}
	return id, true
}

// ─── Teacher endpoints ────────────────────────────────────────────────────────

// GetCourseQuizAnalytics godoc
// @Summary      Quiz performance analytics for a course
// @Description  Returns a performance summary (avg score, pass rate, unique students …)
//               for every quiz in the course. Caller must own the course or be ADMIN.
// @Tags         Analytics
// @Produce      json
// @Param        courseId path int true "Course ID"
// @Security     BearerAuth
// @Success      200 {array}  dto.QuizPerformanceSummary
// @Failure      400 {object} dto.ErrorResponse
// @Failure      403 {object} dto.ErrorResponse
// @Failure      500 {object} dto.ErrorResponse
// @Router       /courses/{courseId}/quiz-analytics [get]
func (h *AnalyticsHandler) GetCourseQuizAnalytics(c *gin.Context) {
	courseID, ok := getCourseIDParam(c)
	if !ok {
		return
	}

	userID := c.MustGet("user_id").(int64)
	userRole := c.MustGet("user_role").(string)

	if err := h.analyticsService.VerifyCourseOwnership(c.Request.Context(), courseID, userID, userRole); err != nil {
		c.JSON(http.StatusForbidden, dto.NewErrorResponse("forbidden", err.Error()))
		return
	}

	data, err := h.analyticsService.GetCourseQuizAnalytics(c.Request.Context(), courseID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, dto.NewErrorResponse("internal_error", "Failed to retrieve quiz analytics"))
		return
	}

	c.JSON(http.StatusOK, data)
}

// GetQuizAllAttempts godoc
// @Summary      All student attempts for a quiz
// @Description  Returns every SUBMITTED / GRADED attempt with student details.
//               Caller must own the course that contains the quiz, or be ADMIN.
// @Tags         Analytics
// @Produce      json
// @Param        quizId path int true "Quiz ID"
// @Security     BearerAuth
// @Success      200 {array}  dto.StudentAttemptOverview
// @Failure      400 {object} dto.ErrorResponse
// @Failure      403 {object} dto.ErrorResponse
// @Failure      500 {object} dto.ErrorResponse
// @Router       /quizzes/{quizId}/all-attempts [get]
func (h *AnalyticsHandler) GetQuizAllAttempts(c *gin.Context) {
	quizID, ok := getQuizIDParam(c)
	if !ok {
		return
	}

	userID := c.MustGet("user_id").(int64)
	userRole := c.MustGet("user_role").(string)

	if err := h.analyticsService.VerifyQuizCourseOwnership(c.Request.Context(), quizID, userID, userRole); err != nil {
		c.JSON(http.StatusForbidden, dto.NewErrorResponse("forbidden", err.Error()))
		return
	}

	data, err := h.analyticsService.GetQuizAllAttempts(c.Request.Context(), quizID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, dto.NewErrorResponse("internal_error", "Failed to retrieve attempts"))
		return
	}

	c.JSON(http.StatusOK, data)
}

// GetQuizWrongAnswerStats godoc
// @Summary      Per-question wrong-answer rates for a quiz
// @Description  Returns questions ordered by wrong-answer rate (highest first).
//               Only auto-graded questions (is_correct IS NOT NULL) are counted.
//               Caller must own the course that contains the quiz, or be ADMIN.
// @Tags         Analytics
// @Produce      json
// @Param        quizId path int true "Quiz ID"
// @Security     BearerAuth
// @Success      200 {array}  dto.WrongAnswerStat
// @Failure      400 {object} dto.ErrorResponse
// @Failure      403 {object} dto.ErrorResponse
// @Failure      500 {object} dto.ErrorResponse
// @Router       /quizzes/{quizId}/wrong-answer-stats [get]
func (h *AnalyticsHandler) GetQuizWrongAnswerStats(c *gin.Context) {
	quizID, ok := getQuizIDParam(c)
	if !ok {
		return
	}

	userID := c.MustGet("user_id").(int64)
	userRole := c.MustGet("user_role").(string)

	if err := h.analyticsService.VerifyQuizCourseOwnership(c.Request.Context(), quizID, userID, userRole); err != nil {
		c.JSON(http.StatusForbidden, dto.NewErrorResponse("forbidden", err.Error()))
		return
	}

	data, err := h.analyticsService.GetQuizWrongAnswerStats(c.Request.Context(), quizID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, dto.NewErrorResponse("internal_error", "Failed to retrieve wrong answer stats"))
		return
	}

	c.JSON(http.StatusOK, data)
}

// GetStudentProgressOverview godoc
// @Summary      All enrolled students' progress in a course
// @Description  Returns one row per ACCEPTED student: mandatory-content completion
//               percentage and quiz score average. Ordered by progress desc.
//               Caller must own the course or be ADMIN.
// @Tags         Analytics
// @Produce      json
// @Param        courseId path int true "Course ID"
// @Security     BearerAuth
// @Success      200 {array}  dto.CourseStudentProgress
// @Failure      400 {object} dto.ErrorResponse
// @Failure      403 {object} dto.ErrorResponse
// @Failure      500 {object} dto.ErrorResponse
// @Router       /courses/{courseId}/student-progress-overview [get]
func (h *AnalyticsHandler) GetStudentProgressOverview(c *gin.Context) {
	courseID, ok := getCourseIDParam(c)
	if !ok {
		return
	}

	userID := c.MustGet("user_id").(int64)
	userRole := c.MustGet("user_role").(string)

	if err := h.analyticsService.VerifyCourseOwnership(c.Request.Context(), courseID, userID, userRole); err != nil {
		c.JSON(http.StatusForbidden, dto.NewErrorResponse("forbidden", err.Error()))
		return
	}

	data, err := h.analyticsService.GetCourseStudentProgressOverview(c.Request.Context(), courseID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, dto.NewErrorResponse("internal_error", "Failed to retrieve student progress"))
		return
	}

	c.JSON(http.StatusOK, data)
}

// ─── Student endpoint ─────────────────────────────────────────────────────────

// GetMyQuizScores godoc
// @Summary      My quiz scores in a course
// @Description  Returns the best attempt per quiz for the authenticated student,
//               along with status: not_started | in_progress | passed | failed | submitted.
// @Tags         Analytics
// @Produce      json
// @Param        courseId path int true "Course ID"
// @Security     BearerAuth
// @Success      200 {array}  dto.StudentQuizScore
// @Failure      400 {object} dto.ErrorResponse
// @Failure      500 {object} dto.ErrorResponse
// @Router       /courses/{courseId}/my-quiz-scores [get]
func (h *AnalyticsHandler) GetMyQuizScores(c *gin.Context) {
	courseID, ok := getCourseIDParam(c)
	if !ok {
		return
	}

	userID := c.MustGet("user_id").(int64)

	data, err := h.analyticsService.GetMyQuizScores(c.Request.Context(), courseID, userID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, dto.NewErrorResponse("internal_error", "Failed to retrieve quiz scores"))
		return
	}

	c.JSON(http.StatusOK, data)
}

// GetStudentWeaknesses godoc
// @Summary      Get the student's weak knowledge nodes
// @Description  Returns weak nodes and overall error percentage for a student in a course
// @Tags         Analytics
// @Produce      json
// @Param        courseId path int true "Course ID"
// @Security     BearerAuth
// @Success      200 {object} dto.StudentWeaknessOverview
// @Failure      400 {object} dto.ErrorResponse
// @Failure      500 {object} dto.ErrorResponse
// @Router       /courses/{courseId}/analytics/weaknesses [get]
func (h *AnalyticsHandler) GetStudentWeaknesses(c *gin.Context) {
	courseID, ok := getCourseIDParam(c)
	if !ok {
		return
	}

	userID := c.MustGet("user_id").(int64)

	data, err := h.analyticsService.GetCourseStudentWeaknesses(c.Request.Context(), courseID, userID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, dto.NewErrorResponse("internal_error", "Failed to retrieve student weaknesses"))
		return
	}

	c.JSON(http.StatusOK, dto.NewDataResponse(data))
}

// GetFlashcardStats godoc
// @Summary      Get Spaced Repetition (SM-2) stats for flashcards
// @Description  Returns counts of due, upcoming, and total learning flashcards for a student
// @Tags         Analytics
// @Produce      json
// @Param        courseId path int true "Course ID"
// @Security     BearerAuth
// @Success      200 {object} dto.FlashcardStatsResponse
// @Failure      400 {object} dto.ErrorResponse
// @Failure      500 {object} dto.ErrorResponse
// @Router       /courses/{courseId}/analytics/flashcard-stats [get]
func (h *AnalyticsHandler) GetFlashcardStats(c *gin.Context) {
	courseID, ok := getCourseIDParam(c)
	if !ok {
		return
	}

	userID := c.MustGet("user_id").(int64)

	data, err := h.analyticsService.GetFlashcardStats(c.Request.Context(), courseID, userID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, dto.NewErrorResponse("internal_error", "Failed to retrieve flashcard stats"))
		return
	}

	c.JSON(http.StatusOK, dto.NewDataResponse(data))
}