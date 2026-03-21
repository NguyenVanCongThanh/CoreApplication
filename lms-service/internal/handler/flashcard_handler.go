package handler

import (
	"net/http"
	"strconv"

	"github.com/gin-gonic/gin"

	"example/hello/internal/dto"
	"example/hello/internal/service"
	"example/hello/pkg/logger"
)

type FlashcardHandler struct {
	flashcardService *service.FlashcardService
	enrollmentSvc    *service.EnrollmentService
}

func NewFlashcardHandler(flashcardService *service.FlashcardService, enrollmentSvc *service.EnrollmentService) *FlashcardHandler {
	return &FlashcardHandler{
		flashcardService: flashcardService,
		enrollmentSvc:    enrollmentSvc,
	}
}

// GenerateFlashcards POST /api/v1/courses/:courseId/nodes/:nodeId/flashcards/generate
func (h *FlashcardHandler) GenerateFlashcards(c *gin.Context) {
	studentID := c.MustGet("user_id").(int64)
	courseID, _ := strconv.ParseInt(c.Param("courseId"), 10, 64)
	nodeID, _ := strconv.ParseInt(c.Param("nodeId"), 10, 64)

	var req dto.GenerateFlashcardsRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, dto.NewErrorResponse("invalid_request", err.Error()))
		return
	}

	// Verify course access
	if err := h.enrollmentSvc.VerifyAccess(c.Request.Context(), studentID, courseID); err != nil {
		c.JSON(http.StatusForbidden, dto.NewErrorResponse("forbidden", "Bạn không có quyền truy cập khóa học này"))
		return
	}

	results, err := h.flashcardService.GenerateFlashcards(c.Request.Context(), studentID, courseID, nodeID, req)
	if err != nil {
		logger.Error("Failed to generate flashcards", err)
		c.JSON(http.StatusInternalServerError, dto.NewErrorResponse("internal_error", err.Error()))
		return
	}

	c.JSON(http.StatusOK, dto.NewDataResponse(results))
}

// ListDueFlashcards GET /api/v1/courses/:courseId/flashcards/due
func (h *FlashcardHandler) ListDueFlashcards(c *gin.Context) {
	studentID := c.MustGet("user_id").(int64)
	courseID, _ := strconv.ParseInt(c.Param("courseId"), 10, 64)

	// Verify course access
	if err := h.enrollmentSvc.VerifyAccess(c.Request.Context(), studentID, courseID); err != nil {
		c.JSON(http.StatusForbidden, dto.NewErrorResponse("forbidden", "Bạn không có quyền truy cập khóa học này"))
		return
	}

	results, err := h.flashcardService.ListDueFlashcards(c.Request.Context(), studentID, courseID)
	if err != nil {
		logger.Error("Failed to list due flashcards", err)
		c.JSON(http.StatusInternalServerError, dto.NewErrorResponse("internal_error", err.Error()))
		return
	}

	c.JSON(http.StatusOK, dto.NewDataResponse(results))
}

// ReviewFlashcard POST /api/v1/flashcards/:flashcardId/review
func (h *FlashcardHandler) ReviewFlashcard(c *gin.Context) {
	studentID := c.MustGet("user_id").(int64)
	flashcardID, _ := strconv.ParseInt(c.Param("flashcardId"), 10, 64)

	var req dto.ReviewFlashcardRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, dto.NewErrorResponse("invalid_request", err.Error()))
		return
	}

	result, err := h.flashcardService.ReviewFlashcard(c.Request.Context(), studentID, flashcardID, req)
	if err != nil {
		logger.Error("Failed to review flashcard", err)
		c.JSON(http.StatusInternalServerError, dto.NewErrorResponse("internal_error", err.Error()))
		return
	}

	c.JSON(http.StatusOK, dto.NewDataResponse(result))
}
