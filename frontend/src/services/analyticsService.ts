import { lmsApiClient } from "./lmsApiClient";

/**
 * analyticsService.ts
 *
 * Handles analytics data for both teachers and students.
 *
 * ─── Backend endpoints needed ──────────────────────────────────────────────
 * GET  /courses/{courseId}/quiz-analytics          → Teacher: quiz performance summary
 * GET  /courses/{courseId}/student-progress-overview  → Teacher: all students progress
 * GET  /quizzes/{quizId}/all-attempts              → Teacher: all student attempts for a quiz
 * GET  /courses/{courseId}/my-quiz-scores          → Student: own quiz scores in course
 * ───────────────────────────────────────────────────────────────────────────
 */

// ─── Types ────────────────────────────────────────────────────────────────────

export interface QuizPerformanceSummary {
  quiz_id: number;
  quiz_title: string;
  content_id: number;
  total_attempts: number;
  unique_students: number;
  avg_score: number;
  avg_percentage: number;
  pass_rate: number;
  passing_score: number | null;
}

export interface StudentAttemptOverview {
  student_id: number;
  student_name: string;
  student_email: string;
  quiz_id: number;
  quiz_title: string;
  attempt_number: number;
  earned_points: number;
  total_points: number;
  percentage: number;
  is_passed: boolean | null;
  status: string;
  submitted_at: string | null;
}

export interface CourseStudentProgress {
  student_id: number;
  student_name: string;
  student_email: string;
  completed_content: number;
  total_mandatory: number;
  progress_percent: number;
  quiz_avg_score: number | null;
  last_activity: string | null;
}

export interface StudentQuizScore {
  quiz_id: number;
  quiz_title: string;
  best_percentage: number | null;
  best_points: number | null;
  total_points: number;
  attempts_count: number;
  is_passed: boolean | null;
  passing_score: number | null;
  last_attempt_at: string | null;
  status: "not_started" | "in_progress" | "submitted" | "passed" | "failed";
}

export interface WrongAnswerStat {
  question_id: number;
  question_text: string;
  question_type: string;
  total_answers: number;
  wrong_count: number;
  wrong_rate: number;
}

export interface WeakNode {
  node_id: number;
  node_name: string;
  total_attempt: number;
  mastery_level: number;
  status_level: "Rất tốt" | "TB" | "Yếu" | "Cần cải thiện";
  wrong_count: number;
}

export interface WeaknessOverviewResponse {
  course_id: number;
  total_wrong_percent: number;
  weak_nodes: WeakNode[];
}

export interface FlashcardStatsResponse {
  today_due_count: number;
  upcoming_count: number;
  learning_count: number;
}

class AnalyticsService {
  // ─── Teacher endpoints ──────────────────────────────────────────────────

  /** Get aggregated quiz performance for all quizzes in a course */
  async getCourseQuizAnalytics(courseId: number): Promise<{ data: QuizPerformanceSummary[] }> {
    const response = await lmsApiClient.get(`/courses/${courseId}/quiz-analytics`);
    return response.data;
  }

  /** Get all student attempts for a specific quiz (teacher view) */
  async getQuizAllAttempts(quizId: number): Promise<{ data: StudentAttemptOverview[] }> {
    const response = await lmsApiClient.get(`/quizzes/${quizId}/all-attempts`);
    return response.data;
  }

  /** Get student progress overview for all enrolled students in a course */
  async getCourseStudentProgressOverview(courseId: number): Promise<{ data: CourseStudentProgress[] }> {
    const response = await lmsApiClient.get(`/courses/${courseId}/student-progress-overview`);
    return response.data;
  }

  /** Get common wrong answers for a quiz */
  async getQuizWrongAnswerStats(quizId: number): Promise<{ data: WrongAnswerStat[] }> {
    const response = await lmsApiClient.get(`/quizzes/${quizId}/wrong-answer-stats`);
    return response.data;
  }

  // ─── Student endpoints ──────────────────────────────────────────────────

  /** Get student's own quiz scores in a course */
  async getMyQuizScores(courseId: number): Promise<{ data: StudentQuizScore[] }> {
    const response = await lmsApiClient.get(`/courses/${courseId}/my-quiz-scores`);
    return response.data;
  }

  /** Get student's weakness overview */
  async getMyWeaknesses(courseId: number): Promise<{ data: WeaknessOverviewResponse }> {
    const response = await lmsApiClient.get(`/courses/${courseId}/analytics/weaknesses`);
    return response.data;
  }

  /** Get flashcard spaced repetition stats */
  async getFlashcardStats(courseId: number): Promise<{ data: FlashcardStatsResponse }> {
    const response = await lmsApiClient.get(`/courses/${courseId}/analytics/flashcard-stats`);
    return response.data;
  }
}

export const analyticsService = new AnalyticsService();
export default analyticsService;