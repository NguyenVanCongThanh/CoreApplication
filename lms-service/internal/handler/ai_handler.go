// lms-service/internal/handler/ai_handler.go
// HTTP handlers for AI features exposed to the Next.js frontend.
// These proxy/orchestrate calls between the student, LMS DB, and ai-service.
package handler

import (
	"encoding/json"
	"fmt"
	"net/http"
	"strconv"

	"example/hello/internal/dto"
	"example/hello/internal/repository"
	"example/hello/pkg/ai"
	"example/hello/pkg/logger"

	"github.com/gin-gonic/gin"
)

// AIHandler handles all AI-related HTTP endpoints.
type AIHandler struct {
	aiClient   *ai.Client
	courseRepo *repository.CourseRepository
}

// NewAIHandler creates a new AIHandler.
func NewAIHandler(aiClient *ai.Client, courseRepo *repository.CourseRepository) *AIHandler {
	return &AIHandler{aiClient: aiClient, courseRepo: courseRepo}
}

// ── Phase 1: Error Diagnosis ──────────────────────────────────────────────────

// DiagnoseWrongAnswer godoc
// @Summary      AI Error Diagnosis
// @Description  Analyze why a student answered incorrectly, with deep link to source material.
//               Called automatically when student submits a wrong answer.
// @Tags         AI - Phase 1
// @Produce      json
// @Param        attemptId path  int true "Quiz Attempt ID"
// @Param        questionId path int true "Question ID"
// @Security     BearerAuth
// @Success      200 {object} ai.DiagnoseResponse
// @Failure      500 {object} dto.ErrorResponse
// @Router       /attempts/{attemptId}/questions/{questionId}/diagnose [post]
func (h *AIHandler) DiagnoseWrongAnswer(c *gin.Context) {
	attemptID, _ := strconv.ParseInt(c.Param("attemptId"), 10, 64)
	questionID, _ := strconv.ParseInt(c.Param("questionId"), 10, 64)
	studentID := c.MustGet("user_id").(int64)

	var body struct {
		WrongAnswer string `json:"wrong_answer" binding:"required"`
		CourseID    int64  `json:"course_id"    binding:"required"`
	}
	if err := c.ShouldBindJSON(&body); err != nil {
		c.JSON(http.StatusBadRequest, dto.NewErrorResponse("invalid_request", err.Error()))
		return
	}

	result, err := h.aiClient.DiagnoseError(c.Request.Context(), ai.DiagnoseRequest{
		StudentID:   studentID,
		AttemptID:   attemptID,
		QuestionID:  questionID,
		WrongAnswer: body.WrongAnswer,
		CourseID:    body.CourseID,
	})
	if err != nil {
		logger.Error("AI diagnosis failed", err)
		c.JSON(http.StatusInternalServerError, dto.NewErrorResponse("ai_error", "Diagnosis unavailable"))
		return
	}

	// Enrich suggested documents with File URL and Title
	if result.SuggestedDocuments != nil {
		for i, doc := range result.SuggestedDocuments {
			if contentIDVal, ok := doc["content_id"].(float64); ok {
				contentID := int64(contentIDVal)
				content, err := h.courseRepo.GetContentByID(c.Request.Context(), contentID)
				if err == nil && content != nil {
					// Add file info
					if content.FilePath.Valid {
						doc["file_url"] = "/api/v1/files/serve/" + content.FilePath.String
					}
					doc["title"] = content.Title
					doc["content_type"] = content.Type
					result.SuggestedDocuments[i] = doc
				}
			}
		}
	}

	c.JSON(http.StatusOK, dto.NewDataResponse(result))
}

// GetClassHeatmap godoc
// @Summary      Class Knowledge Heatmap
// @Description  Returns knowledge nodes sorted by class-wide wrong rate. Teacher/Admin only.
// @Tags         AI - Phase 1
// @Produce      json
// @Param        courseId path int true "Course ID"
// @Security     BearerAuth
// @Success      200 {array} ai.HeatmapNode
// @Router       /courses/{courseId}/ai/heatmap [get]
func (h *AIHandler) GetClassHeatmap(c *gin.Context) {
	courseID, _ := strconv.ParseInt(c.Param("courseId"), 10, 64)

	data, err := h.aiClient.GetClassHeatmap(c.Request.Context(), courseID)
	if err != nil {
		logger.Error("Heatmap failed", err)
		c.JSON(http.StatusInternalServerError, dto.NewErrorResponse("ai_error", err.Error()))
		return
	}

	c.JSON(http.StatusOK, dto.NewDataResponse(data))
}

// GetStudentHeatmap godoc
// @Summary      Student Knowledge Map
// @Description  Returns per-student knowledge mastery across all nodes in a course.
// @Tags         AI - Phase 1
// @Produce      json
// @Param        courseId path int true "Course ID"
// @Security     BearerAuth
// @Success      200 {array} map[string]interface{}
// @Router       /courses/{courseId}/ai/my-heatmap [get]
func (h *AIHandler) GetStudentHeatmap(c *gin.Context) {
	courseID, _ := strconv.ParseInt(c.Param("courseId"), 10, 64)
	studentID := c.MustGet("user_id").(int64)

	data, err := h.aiClient.GetStudentHeatmap(c.Request.Context(), studentID, courseID)
	if err != nil {
		logger.Error("Student heatmap failed", err)
		c.JSON(http.StatusInternalServerError, dto.NewErrorResponse("ai_error", err.Error()))
		return
	}

	c.JSON(http.StatusOK, dto.NewDataResponse(data))
}

// ── Knowledge Nodes ────────────────────────────────────────────────────────────

// CreateKnowledgeNode godoc
// @Summary      Create Knowledge Node
// @Description  Create an atomic knowledge unit for a course (Teacher/Admin only).
// @Tags         AI - Knowledge Graph
// @Accept       json
// @Produce      json
// @Param        courseId path int true "Course ID"
// @Security     BearerAuth
// @Success      201 {object} map[string]interface{}
// @Router       /courses/{courseId}/ai/nodes [post]
func (h *AIHandler) CreateKnowledgeNode(c *gin.Context) {
	courseID, _ := strconv.ParseInt(c.Param("courseId"), 10, 64)

	var body struct {
		Name        string `json:"name"        binding:"required"`
		NameVI      string `json:"name_vi"`
		NameEN      string `json:"name_en"`
		Description string `json:"description"`
		ParentID    *int64 `json:"parent_id"`
		OrderIndex  int    `json:"order_index"`
	}
	if err := c.ShouldBindJSON(&body); err != nil {
		c.JSON(http.StatusBadRequest, dto.NewErrorResponse("invalid_request", err.Error()))
		return
	}

	result, err := h.aiClient.CreateKnowledgeNode(c.Request.Context(), ai.CreateNodeRequest{
		CourseID:    courseID,
		Name:        body.Name,
		NameVI:      body.NameVI,
		NameEN:      body.NameEN,
		Description: body.Description,
		ParentID:    body.ParentID,
		OrderIndex:  body.OrderIndex,
	})
	if err != nil {
		c.JSON(http.StatusInternalServerError, dto.NewErrorResponse("ai_error", err.Error()))
		return
	}

	c.JSON(http.StatusCreated, dto.NewDataResponse(result))
}

// ListKnowledgeNodes godoc
// @Summary      List Knowledge Nodes for a Course
// @Tags         AI - Knowledge Graph
// @Produce      json
// @Param        courseId path int true "Course ID"
// @Security     BearerAuth
// @Success      200 {array} map[string]interface{}
// @Router       /courses/{courseId}/ai/nodes [get]
func (h *AIHandler) ListKnowledgeNodes(c *gin.Context) {
	courseID, _ := strconv.ParseInt(c.Param("courseId"), 10, 64)

	nodes, err := h.aiClient.ListKnowledgeNodes(c.Request.Context(), courseID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, dto.NewErrorResponse("ai_error", err.Error()))
		return
	}

	c.JSON(http.StatusOK, dto.NewDataResponse(nodes))
}

// ── Phase 2: Quiz Generation ───────────────────────────────────────────────────

// GenerateQuiz godoc
// @Summary      AI Auto Quiz Generator (Bloom's Taxonomy)
// @Description  Generate quiz questions for a knowledge node using Bloom's Taxonomy.
//               Questions are saved as DRAFT — require instructor review before publish.
// @Tags         AI - Phase 2
// @Accept       json
// @Produce      json
// @Param        courseId path int true "Course ID"
// @Security     BearerAuth
// @Success      200 {object} ai.GenerateQuizResponse
// @Router       /courses/{courseId}/ai/generate-quiz [post]
func (h *AIHandler) GenerateQuiz(c *gin.Context) {
	courseID, _ := strconv.ParseInt(c.Param("courseId"), 10, 64)
	createdBy := c.MustGet("user_id").(int64)

	var body struct {
		NodeID            int64    `json:"node_id"             binding:"required"`
		BloomLevels       []string `json:"bloom_levels"`
		Language          string   `json:"language"`
		QuestionsPerLevel int      `json:"questions_per_level"`
	}
	if err := c.ShouldBindJSON(&body); err != nil {
		c.JSON(http.StatusBadRequest, dto.NewErrorResponse("invalid_request", err.Error()))
		return
	}

	if body.Language == "" {
		body.Language = "vi"
	}
	if body.QuestionsPerLevel == 0 {
		body.QuestionsPerLevel = 1
	}

	result, err := h.aiClient.GenerateQuiz(c.Request.Context(), ai.GenerateQuizRequest{
		NodeID:            body.NodeID,
		CourseID:          courseID,
		CreatedBy:         createdBy,
		BloomLevels:       body.BloomLevels,
		Language:          body.Language,
		QuestionsPerLevel: body.QuestionsPerLevel,
	})
	if err != nil {
		logger.Error("Quiz generation failed", err)
		c.JSON(http.StatusInternalServerError, dto.NewErrorResponse("ai_error", err.Error()))
		return
	}

	c.JSON(http.StatusOK, dto.NewDataResponse(result))
}

// ListDraftQuestions godoc
// @Summary      List AI-Generated Draft Questions
// @Description  Returns all DRAFT AI questions awaiting instructor review.
// @Tags         AI - Phase 2
// @Produce      json
// @Param        courseId path int    true  "Course ID"
// @Param        node_id  query int   false "Filter by node ID"
// @Security     BearerAuth
// @Success      200 {array} map[string]interface{}
// @Router       /courses/{courseId}/ai/drafts [get]
func (h *AIHandler) ListDraftQuestions(c *gin.Context) {
	courseID, _ := strconv.ParseInt(c.Param("courseId"), 10, 64)

	var nodeID *int64
	if nodeIDStr := c.Query("node_id"); nodeIDStr != "" {
		if n, err := strconv.ParseInt(nodeIDStr, 10, 64); err == nil {
			nodeID = &n
		}
	}

	drafts, err := h.aiClient.GetDraftQuestions(c.Request.Context(), courseID, nodeID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, dto.NewErrorResponse("ai_error", err.Error()))
		return
	}

	c.JSON(http.StatusOK, dto.NewDataResponse(drafts))
}

// ApproveQuestion godoc
// @Summary      Approve AI-Generated Question
// @Description  Instructor approves a DRAFT question → published to a quiz.
// @Tags         AI - Phase 2
// @Accept       json
// @Produce      json
// @Param        genId path int true "Generation ID"
// @Security     BearerAuth
// @Router       /ai/quiz-drafts/{genId}/approve [post]
func (h *AIHandler) ApproveQuestion(c *gin.Context) {
	genID, _ := strconv.ParseInt(c.Param("genId"), 10, 64)
	reviewerID := c.MustGet("user_id").(int64)

	var body struct {
		QuizID     int64  `json:"quiz_id"     binding:"required"`
		ReviewNote string `json:"review_note"`
	}
	if err := c.ShouldBindJSON(&body); err != nil {
		c.JSON(http.StatusBadRequest, dto.NewErrorResponse("invalid_request", err.Error()))
		return
	}

	qID, err := h.aiClient.ApproveQuestion(c.Request.Context(), genID, ai.ApproveQuestionRequest{
		ReviewerID: reviewerID,
		QuizID:     body.QuizID,
		ReviewNote: body.ReviewNote,
	})
	if err != nil {
		c.JSON(http.StatusInternalServerError, dto.NewErrorResponse("ai_error", err.Error()))
		return
	}

	c.JSON(http.StatusOK, dto.NewDataResponse(map[string]int64{"quiz_question_id": qID}))
}

// RejectQuestion godoc
// @Summary      Reject AI-Generated Question
// @Tags         AI - Phase 2
// @Accept       json
// @Produce      json
// @Param        genId path int true "Generation ID"
// @Security     BearerAuth
// @Router       /ai/quiz-drafts/{genId}/reject [post]
func (h *AIHandler) RejectQuestion(c *gin.Context) {
	genID, _ := strconv.ParseInt(c.Param("genId"), 10, 64)
	reviewerID := c.MustGet("user_id").(int64)

	var body struct {
		ReviewNote string `json:"review_note" binding:"required"`
	}
	if err := c.ShouldBindJSON(&body); err != nil {
		c.JSON(http.StatusBadRequest, dto.NewErrorResponse("invalid_request", err.Error()))
		return
	}

	err := h.aiClient.RejectQuestion(c.Request.Context(), genID, ai.RejectQuestionRequest{
		ReviewerID: reviewerID,
		ReviewNote: body.ReviewNote,
	})
	if err != nil {
		c.JSON(http.StatusInternalServerError, dto.NewErrorResponse("ai_error", err.Error()))
		return
	}

	c.JSON(http.StatusOK, dto.NewMessageResponse("Question rejected"))
}

// ── Phase 2: Spaced Repetition ─────────────────────────────────────────────────

// GetDueReviews godoc
// @Summary      Get Due Review Questions (Spaced Repetition)
// @Description  Returns questions due for review today based on SM-2 algorithm.
//               Used for the 5-minute warm-up session on student login.
// @Tags         AI - Phase 2
// @Produce      json
// @Param        courseId path int true "Course ID"
// @Security     BearerAuth
// @Router       /courses/{courseId}/ai/reviews/due [get]
func (h *AIHandler) GetDueReviews(c *gin.Context) {
	courseID, _ := strconv.ParseInt(c.Param("courseId"), 10, 64)
	studentID := c.MustGet("user_id").(int64)

	reviews, err := h.aiClient.GetDueReviews(c.Request.Context(), studentID, courseID, 20)
	if err != nil {
		c.JSON(http.StatusInternalServerError, dto.NewErrorResponse("ai_error", err.Error()))
		return
	}

	c.JSON(http.StatusOK, dto.NewDataResponse(reviews))
}

// RecordReviewResponse godoc
// @Summary      Record Spaced Repetition Response
// @Description  Record student quality rating (0-5) for a review question. Updates SM-2 schedule.
// @Tags         AI - Phase 2
// @Accept       json
// @Produce      json
// @Param        courseId path int true "Course ID"
// @Security     BearerAuth
// @Router       /courses/{courseId}/ai/reviews/record [post]
func (h *AIHandler) RecordReviewResponse(c *gin.Context) {
	courseID, _ := strconv.ParseInt(c.Param("courseId"), 10, 64)
	studentID := c.MustGet("user_id").(int64)

	var body struct {
		QuestionID int64  `json:"question_id" binding:"required"`
		NodeID     *int64 `json:"node_id"`
		Quality    int    `json:"quality" binding:"required,min=0,max=5"`
	}
	if err := c.ShouldBindJSON(&body); err != nil {
		c.JSON(http.StatusBadRequest, dto.NewErrorResponse("invalid_request", err.Error()))
		return
	}

	result, err := h.aiClient.RecordReviewResponse(c.Request.Context(), ai.RecordReviewRequest{
		StudentID:  studentID,
		QuestionID: body.QuestionID,
		CourseID:   courseID,
		NodeID:     body.NodeID,
		Quality:    body.Quality,
	})
	if err != nil {
		c.JSON(http.StatusInternalServerError, dto.NewErrorResponse("ai_error", err.Error()))
		return
	}

	c.JSON(http.StatusOK, dto.NewDataResponse(result))
}

// GetReviewStats godoc
// @Summary      Spaced Repetition Stats
// @Tags         AI - Phase 2
// @Produce      json
// @Param        courseId path int true "Course ID"
// @Security     BearerAuth
// @Router       /courses/{courseId}/ai/reviews/stats [get]
func (h *AIHandler) GetReviewStats(c *gin.Context) {
	courseID, _ := strconv.ParseInt(c.Param("courseId"), 10, 64)
	studentID := c.MustGet("user_id").(int64)

	stats, err := h.aiClient.GetReviewStats(c.Request.Context(), studentID, courseID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, dto.NewErrorResponse("ai_error", err.Error()))
		return
	}

	c.JSON(http.StatusOK, dto.NewDataResponse(stats))
}

func (h *AIHandler) TriggerDocumentProcess(c *gin.Context) {
    contentID, _ := strconv.ParseInt(c.Param("contentId"), 10, 64)
    
    var body struct {
        CourseID    int64  `json:"course_id" binding:"required"`
        NodeID      *int64 `json:"node_id"`
        FileURL     string `json:"file_url"`
        ContentType string `json:"content_type"`
    }
    if err := c.ShouldBindJSON(&body); err != nil {
        c.JSON(http.StatusBadRequest, dto.NewErrorResponse("invalid_request", err.Error()))
        return
    }
    if body.ContentType == "" {
        body.ContentType = "application/pdf"
    }

    result, err := h.aiClient.ProcessDocument(c.Request.Context(), ai.ProcessDocumentRequest{
        ContentID:   contentID,
        CourseID:    body.CourseID,
        NodeID:      body.NodeID,
        FileURL:     body.FileURL,
        ContentType: body.ContentType,
    })
    if err != nil {
        logger.Error("Document processing trigger failed", err)
        c.JSON(http.StatusInternalServerError, dto.NewErrorResponse("ai_error", err.Error()))
        return
    }
    c.JSON(http.StatusAccepted, dto.NewDataResponse(result))
}

// TriggerContentAutoIndex godoc
// @Summary      Trigger auto-index for a content document
// @Description  Giáo viên click nút "Index" → AI tự động tạo knowledge nodes.
//               Trả về ngay; frontend poll /content/:id/ai-index-status.
// @Tags         AI - Auto Index
// @Accept       json
// @Produce      json
// @Param        contentId path int true "Content ID"
// @Security     BearerAuth
// @Success      202 {object} map[string]interface{}
// @Router       /content/{contentId}/ai-index [post]
func (h *AIHandler) TriggerContentAutoIndex(c *gin.Context) {
	contentID, err := strconv.ParseInt(c.Param("contentId"), 10, 64)
	if err != nil {
		c.JSON(http.StatusBadRequest, dto.NewErrorResponse("invalid_id", "Invalid content ID"))
		return
	}
 
	userID := c.MustGet("user_id").(int64)
	userRole := c.GetString("user_role")
 
	// Lấy content để verify quyền và lấy file_path
	content, err := h.courseRepo.GetContentByID(c.Request.Context(), contentID)
	if err != nil {
		logger.Error(fmt.Sprintf("Auto-index: Content %d not found", contentID), err)
		c.JSON(http.StatusNotFound, dto.NewErrorResponse("not_found", "Content not found"))
		return
	}
 
	// Log content details for debugging
	logger.Info(fmt.Sprintf("Auto-index debug: ContentID=%d, Type=%s, FilePath.Valid=%v, FilePath.String='%s'", 
		contentID, content.Type, content.FilePath.Valid, content.FilePath.String))

	// Chỉ TEACHER hoặc ADMIN mới được index
	if userRole != "ADMIN" {
		// Verify ownership qua section → course
		section, sErr := h.courseRepo.GetSectionByID(c.Request.Context(), content.SectionID)
		if sErr != nil {
			logger.Error(fmt.Sprintf("Auto-index: Section %d fetch failed", content.SectionID), sErr)
			c.JSON(http.StatusInternalServerError, dto.NewErrorResponse("internal_error", sErr.Error()))
			return
		}
		course, cErr := h.courseRepo.GetByID(c.Request.Context(), section.CourseID)
		if cErr != nil {
			logger.Error(fmt.Sprintf("Auto-index: Course %d fetch failed", section.CourseID), cErr)
			c.JSON(http.StatusInternalServerError, dto.NewErrorResponse("internal_error", cErr.Error()))
			return
		}
		if course.CreatedBy != userID {
			logger.Warn(fmt.Sprintf("Auto-index: User %d not authorized for course %d", userID, course.ID))
			c.JSON(http.StatusForbidden, dto.NewErrorResponse("forbidden", "Only course owner can index documents"))
			return
		}
	}
 
	// Kiểm tra content có file không
	finalFilePath := ""
	finalFileType := "application/pdf"

	if content.FilePath.Valid && content.FilePath.String != "" {
		finalFilePath = content.FilePath.String
		if content.FileType.Valid {
			finalFileType = content.FileType.String
		}
	} else if len(content.Metadata) > 0 {
		// Fallback: Thử lấy từ metadata JSON
		var meta map[string]interface{}
		if err := json.Unmarshal(content.Metadata, &meta); err == nil {
			if path, ok := meta["file_path"].(string); ok && path != "" {
				finalFilePath = path
				logger.Info(fmt.Sprintf("Auto-index fallback: Using file_path from metadata for content %d: %s", contentID, path))
			}
			if ftype, ok := meta["file_type"].(string); ok && ftype != "" {
				finalFileType = ftype
			}
		}
	}

	if finalFilePath == "" {
		// Thêm log để biết chính xác lỗi 400 từ đây
		logger.Warn(fmt.Sprintf("Auto-index fail: Content %d (Type: %s) has no file_path in column or metadata", 
			contentID, content.Type))
		c.JSON(http.StatusBadRequest, dto.NewErrorResponse("no_file", "Content has no file to index"))
		return
	}
 
	// Xác định courseID từ section
	section, _ := h.courseRepo.GetSectionByID(c.Request.Context(), content.SectionID)
	course, _ := h.courseRepo.GetByID(c.Request.Context(), section.CourseID)
 
	// Gọi AI service
	resp, err := h.aiClient.AutoIndex(c.Request.Context(), ai.AutoIndexRequest{
		ContentID:   contentID,
		CourseID:    course.ID,
		FileURL:     finalFilePath,
		ContentType: finalFileType,
	})
	if err != nil {
		logger.Error("Auto-index trigger failed", err)
		// Vẫn trả về thông báo lỗi nhưng không fail request
		c.JSON(http.StatusServiceUnavailable, dto.NewErrorResponse("ai_unavailable", err.Error()))
		return
	}
 
	c.JSON(http.StatusAccepted, dto.NewDataResponse(map[string]interface{}{
		"job_id":     resp.JobID,
		"content_id": contentID,
		"status":     resp.Status,
	}))
}
 
// GetContentAutoIndexStatus godoc
// @Summary      Get auto-index status for a content item
// @Tags         AI - Auto Index
// @Produce      json
// @Param        contentId path int true "Content ID"
// @Security     BearerAuth
// @Router       /content/{contentId}/ai-index-status [get]
func (h *AIHandler) GetContentAutoIndexStatus(c *gin.Context) {
	contentID, err := strconv.ParseInt(c.Param("contentId"), 10, 64)
	if err != nil {
		c.JSON(http.StatusBadRequest, dto.NewErrorResponse("invalid_id", "Invalid content ID"))
		return
	}
 
	status, err := h.aiClient.GetAutoIndexStatus(c.Request.Context(), contentID)
	if err != nil {
		// Fallback: đọc thẳng từ DB nếu AI service không available
		dbStatus, _, dbErr := h.courseRepo.GetContentAIIndexStatus(c.Request.Context(), contentID)
		if dbErr != nil {
			c.JSON(http.StatusInternalServerError, dto.NewErrorResponse("internal_error", dbErr.Error()))
			return
		}
		c.JSON(http.StatusOK, dto.NewDataResponse(map[string]string{
			"status": dbStatus,
		}))
		return
	}
 
	c.JSON(http.StatusOK, dto.NewDataResponse(status))
}
 
// GetCourseKnowledgeGraph godoc
// @Summary      Get knowledge graph for a course
// @Tags         AI - Auto Index
// @Produce      json
// @Param        courseId path int true "Course ID"
// @Security     BearerAuth
// @Router       /courses/{courseId}/ai/knowledge-graph [get]
func (h *AIHandler) GetCourseKnowledgeGraph(c *gin.Context) {
	courseID, _ := strconv.ParseInt(c.Param("courseId"), 10, 64)
 
	graph, err := h.aiClient.GetKnowledgeGraph(c.Request.Context(), courseID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, dto.NewErrorResponse("ai_error", err.Error()))
		return
	}
 
	c.JSON(http.StatusOK, dto.NewDataResponse(graph))
}