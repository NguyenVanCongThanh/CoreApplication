import { lmsApiClient } from "./lmsApiClient";

export interface Flashcard {
  id: number;
  node_id: number;
  course_id: number;
  front_text: string;
  back_text: string;
  language: string;
}

export interface FlashcardRepetition {
  id: number;
  flashcard_id: number;
  easiness_factor: number;
  interval_days: number;
  repetitions: number;
  next_review_date: string;
  last_reviewed_at: string;
}

export interface FlashcardDueItem {
  id: number;
  course_id: number;
  node_id: number;
  front_text: string;
  back_text: string;
  status: string;
  next_review_date: string;
}

export interface GenerateFlashcardsRequest {
  count: number;
}

class FlashcardService {
  /**
   * Generate highly personalized flashcards given a node
   */
  async generateFlashcards(
    courseId: number,
    nodeId: number,
    req: GenerateFlashcardsRequest
  ): Promise<{ data: Flashcard[] }> {
    const response = await lmsApiClient.post(
      `/courses/${courseId}/nodes/${nodeId}/flashcards/generate`,
      req
    );
    return response.data;
  }

  /**
   * List flashcards due today
   */
  async listDueFlashcards(courseId: number): Promise<{ data: FlashcardDueItem[] }> {
    const response = await lmsApiClient.get(`/courses/${courseId}/flashcards/due`);
    return response.data;
  }

  /**
   * Record a review (0 to 5) for a flashcard
   */
  async reviewFlashcard(flashcardId: number, quality: number): Promise<{ data: FlashcardRepetition }> {
    const response = await lmsApiClient.post(`/flashcards/${flashcardId}/review`, { quality });
    return response.data;
  }
}

export const flashcardService = new FlashcardService();
export default flashcardService;
