/**
 * aiService.ts
 * Frontend client for all AI features (Phase 1 & 2).
 * Calls Go lms-service endpoints which proxy to ai-service internally.
 */
import { lmsApiClient } from "./lmsApiClient";

// ─── Phase 1: Diagnosis ───────────────────────────────────────────────────────

export interface DeepLink {
  content_id?: number;
  source_type: "document" | "video";
  page_number?: number;
  start_time_sec?: number;
  end_time_sec?: number;
  url_fragment?: string; // '#page=5' or '#t=120'
}

export interface DiagnosisResult {
  explanation: string;
  gap_type: "misconception" | "missing_prerequisite" | "careless_error" | "unknown";
  knowledge_gap: string;
  study_suggestion: string;
  confidence: number;
  source_chunk_id?: number;
  deep_link?: DeepLink;
  language: string;
}

export interface HeatmapNode {
  node_id: number;
  node_name: string;
  name_vi?: string;
  student_count: number;
  avg_mastery: number;
  total_wrong: number;
  total_attempts: number;
  wrong_rate: number;
}

// ─── Phase 2: Quiz Gen & Spaced Repetition ─────────────────────────────────

export interface GeneratedQuestion {
  id: number;
  node_id: number;
  node_name?: string;
  course_id: number;
  bloom_level: string;
  question_text: string;
  question_type: string;
  answer_options: { text: string; is_correct: boolean; explanation: string }[];
  explanation: string;
  source_quote: string;
  source_chunk_id?: number;
  language: string;
  status: "DRAFT" | "APPROVED" | "REJECTED" | "PUBLISHED";
  review_note?: string;
}

export interface DueReview {
  question_id: number;
  node_id?: number;
  next_review_date: string;
  interval_days: number;
  repetitions: number;
  question_text: string;
  question_type: string;
  node_name?: string;
}

export interface ReviewStats {
  due_today: number;
  upcoming: number;
  total_tracked: number;
  avg_easiness?: number;
  avg_repetitions?: number;
}

export interface KnowledgeNode {
  id: number;
  course_id: number;
  parent_id?: number;
  name: string;
  name_vi?: string;
  name_en?: string;
  description?: string;
  level: number;
  order_index: number;
  chunk_count: number;
}

class AIService {
  // ─── Diagnosis ─────────────────────────────────────────────────────────────

  async diagnoseWrongAnswer(
    attemptId: number,
    questionId: number,
    wrongAnswer: string,
    courseId: number
  ): Promise<DiagnosisResult> {
    const res = await lmsApiClient.post(
      `/ai/attempts/${attemptId}/questions/${questionId}/diagnose`,
      {
        wrong_answer: wrongAnswer,
        course_id: courseId,
      }
    );
    return res.data?.data ?? res.data;
  }

  async getClassHeatmap(courseId: number): Promise<HeatmapNode[]> {
    const res = await lmsApiClient.get(`/courses/${courseId}/ai/heatmap`);
    return res.data?.data ?? res.data ?? [];
  }

  async getStudentHeatmap(courseId: number): Promise<HeatmapNode[]> {
    const res = await lmsApiClient.get(`/courses/${courseId}/ai/my-heatmap`);
    return res.data?.data ?? res.data ?? [];
  }

  // ─── Knowledge Nodes ──────────────────────────────────────────────────────

  async listKnowledgeNodes(courseId: number): Promise<KnowledgeNode[]> {
    const res = await lmsApiClient.get(`/courses/${courseId}/ai/nodes`);
    return res.data?.data ?? res.data ?? [];
  }

  async createKnowledgeNode(
    courseId: number,
    data: { name: string; name_vi?: string; description?: string; parent_id?: number }
  ): Promise<KnowledgeNode> {
    const res = await lmsApiClient.post(`/courses/${courseId}/ai/nodes`, data);
    return res.data?.data ?? res.data;
  }

  // ─── Quiz Generation ──────────────────────────────────────────────────────

  async generateQuiz(
    courseId: number,
    nodeId: number,
    options?: {
      bloom_levels?: string[];
      language?: string;
      questions_per_level?: number;
    }
  ): Promise<GeneratedQuestion[]> {
    const res = await lmsApiClient.post(`/courses/${courseId}/ai/generate-quiz`, {
      node_id: nodeId,
      ...options,
    });
    return res.data?.data ?? res.data ?? [];
  }

  async listDraftQuestions(courseId: number): Promise<GeneratedQuestion[]> {
    const res = await lmsApiClient.get(`/courses/${courseId}/ai/drafts`);
    return res.data?.data ?? res.data ?? [];
  }

  async approveQuestion(
    genId: number,
    quizId: number,
    reviewNote = ""
  ): Promise<void> {
    await lmsApiClient.post(`/ai/quiz-drafts/${genId}/approve`, {
      quiz_id: quizId,
      review_note: reviewNote,
    });
  }

  async rejectQuestion(genId: number, reviewNote: string): Promise<void> {
    await lmsApiClient.post(`/ai/quiz-drafts/${genId}/reject`, { review_note: reviewNote });
  }

  // ─── Spaced Repetition ────────────────────────────────────────────────────

  async getDueReviews(courseId: number): Promise<DueReview[]> {
    const res = await lmsApiClient.get(`/courses/${courseId}/ai/reviews/due`);
    return res.data?.data ?? res.data ?? [];
  }

  async recordReview(
    courseId: number,
    questionId: number,
    quality: 0 | 1 | 2 | 3 | 4 | 5,
    nodeId?: number
  ): Promise<void> {
    await lmsApiClient.post(`/courses/${courseId}/ai/reviews/record`, {
      question_id: questionId,
      quality,
      node_id: nodeId,
    });
  }

  async getReviewStats(courseId: number): Promise<ReviewStats> {
    const res = await lmsApiClient.get(`/courses/${courseId}/ai/reviews/stats`);
    return res.data?.data ?? res.data ?? { due_today: 0, upcoming: 0, total_tracked: 0 };
  }
}

export const aiService = new AIService();
export default aiService;
