package handler

import (
	"net/http"
	"strconv"

	"example/hello/internal/dto"
	"example/hello/internal/service"

	"github.com/gin-gonic/gin"
)

type ProgressHandler struct {
	progressService *service.ProgressService
}

func NewProgressHandler(progressService *service.ProgressService) *ProgressHandler {
	return &ProgressHandler{progressService: progressService}
}

// MarkComplete godoc
// @Summary      Mark a content item as completed
// @Description  Student marks a mandatory content item as viewed/completed.
//               Non-mandatory items are accepted silently (no DB write).
//               Duplicate calls are idempotent.
// @Tags         Progress
// @Produce      json
// @Param        contentId path int true "Content ID"
// @Security     BearerAuth
// @Success      200 {object} map[string]string
// @Failure      400 {object} dto.ErrorResponse
// @Failure      403 {object} dto.ErrorResponse
// @Router       /content/{contentId}/complete [post]
func (h *ProgressHandler) MarkComplete(c *gin.Context) {
	contentID, err := strconv.ParseInt(c.Param("contentId"), 10, 64)
	if err != nil {
		c.JSON(http.StatusBadRequest, dto.NewErrorResponse("invalid_content_id", "Invalid content ID"))
		return
	}

	userID := c.MustGet("user_id").(int64)

	if err := h.progressService.MarkContentComplete(c.Request.Context(), contentID, userID); err != nil {
		c.JSON(http.StatusForbidden, dto.NewErrorResponse("mark_complete_failed", err.Error()))
		return
	}

	c.JSON(http.StatusOK, gin.H{"message": "Content marked as completed"})
}

// GetMyProgress godoc
// @Summary      Get my course progress summary
// @Description  Returns total/completed mandatory-content counts and IDs.
// @Tags         Progress
// @Produce      json
// @Param        courseId path int true "Course ID"
// @Security     BearerAuth
// @Success      200 {object} dto.CourseProgressResponse
// @Failure      400 {object} dto.ErrorResponse
// @Failure      500 {object} dto.ErrorResponse
// @Router       /courses/{courseId}/my-progress [get]
func (h *ProgressHandler) GetMyProgress(c *gin.Context) {
	courseID, err := strconv.ParseInt(c.Param("courseId"), 10, 64)
	if err != nil {
		c.JSON(http.StatusBadRequest, dto.NewErrorResponse("invalid_course_id", "Invalid course ID"))
		return
	}

	userID := c.MustGet("user_id").(int64)

	progress, err := h.progressService.GetMyCourseProgress(c.Request.Context(), courseID, userID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, dto.NewErrorResponse("internal_error", "Failed to retrieve progress"))
		return
	}

	c.JSON(http.StatusOK, progress)
}

// GetMyProgressDetail godoc
// @Summary      Get detailed per-item course progress
// @Description  Returns every content item with its is_completed flag and timestamp.
// @Tags         Progress
// @Produce      json
// @Param        courseId path int true "Course ID"
// @Security     BearerAuth
// @Success      200 {object} dto.CourseProgressDetailResponse
// @Failure      400 {object} dto.ErrorResponse
// @Failure      500 {object} dto.ErrorResponse
// @Router       /courses/{courseId}/progress-detail [get]
func (h *ProgressHandler) GetMyProgressDetail(c *gin.Context) {
	courseID, err := strconv.ParseInt(c.Param("courseId"), 10, 64)
	if err != nil {
		c.JSON(http.StatusBadRequest, dto.NewErrorResponse("invalid_course_id", "Invalid course ID"))
		return
	}

	userID := c.MustGet("user_id").(int64)

	detail, err := h.progressService.GetMyCourseProgressDetail(c.Request.Context(), courseID, userID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, dto.NewErrorResponse("internal_error", "Failed to retrieve progress detail"))
		return
	}

	c.JSON(http.StatusOK, detail)
}