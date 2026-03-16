/* eslint-disable @next/next/no-img-element */
"use client";

import { useState, useEffect, ReactNode } from "react";
import { Button } from "@/components/ui/button";
import quizService from "@/services/quizService";
import FillBlankTextStudent from "@/components/lms/student/FillBlankTextStudent";
import FillBlankDropdownStudent from "@/components/lms/student/FillBlankDropdownStudent";
import AIDiagnosisModal from "./AIDiagnosisModal";
import {
  CheckCircle,
  XCircle,
  AlertCircle,
  Award,
  MessageSquare,
  Eye,
  FileText,
  Upload,
  Sparkles,
} from "lucide-react";
import type {
  FillBlankTextSettings,
  FillBlankTextCorrectAnswer,
  FillBlankTextStudentAnswer,
  FillBlankDropdownSettings,
  FillBlankDropdownOption,
  FillBlankDropdownStudentAnswer,
} from "@/types";

interface AnswerOption {
  id: number;
  option_text: string;
  is_correct: boolean;
  order_index: number;
  blank_id?: number;
}

interface CorrectAnswer {
  id: number;
  answer_text: string;
  case_sensitive: boolean;
  exact_match: boolean;
  blank_id?: number;
}

interface Question {
  id: number;
  question_type: string;
  question_text: string;
  explanation?: string;
  points: number;
  settings?: any;
  answer_options: AnswerOption[];
  correct_answers: CorrectAnswer[];
  images?: Array<{
    id: string;
    url: string;
    file_name: string;
    position: string;
    caption?: string;
    alt_text?: string;
    display_width?: string;
  }>;
}

interface StudentAnswer {
  id: number;
  answer_data: any;
  points_earned?: number;
  is_correct?: boolean;
  grader_feedback?: string;
}

interface QuestionWithAnswer {
  question: Question;
  student_answer?: StudentAnswer;
}

interface QuizReview {
  attempt: {
    id: number;
    quiz_id: number;
    attempt_number: number;
    started_at: string;
    submitted_at: string;
    earned_points: number;
    total_points: number;
    percentage: number;
    is_passed: boolean;
  };
  quiz: {
    id: number;
    title: string;
    total_points: number;
    passing_score?: number;
  };
  questions_with_answers: QuestionWithAnswer[];
  show_correct_answers: boolean;
  show_feedback: boolean;
}

interface QuizReviewModalProps {
  attemptId: number;
  onClose: () => void;
}

export default function QuizReviewModal({
  attemptId,
  onClose,
}: QuizReviewModalProps) {
  const [review, setReview] = useState<QuizReview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [diagnosisTarget, setDiagnosisTarget] = useState<{ qId: number; text: string } | null>(null);

  useEffect(() => {
    loadReview();
  }, [attemptId]);

  const loadReview = async () => {
    try {
      setLoading(true);
      const response = await quizService.reviewQuiz(attemptId);
      setReview(response.data);
    } catch (err: any) {
      console.error("Error loading quiz review:", err);
      setError(err.response?.data?.error || "Không thể tải bài làm");
    } finally {
      setLoading(false);
    }
  };

  const buildImageUrl = (url: string) => {
    if (url.startsWith("http://") || url.startsWith("https://")) {
      return url;
    }
    return `${url}`;
  };

  const renderQuestionImages = (question: Question, position: "top" | "bottom") => {
    const images = question.images || question.settings?.images || [];
    const filteredImages = images.filter((img: any) => 
      !img.position || img.position === position || 
      (position === "top" && img.position === "above_question") ||
      (position === "bottom" && img.position === "below_question")
    );

    if (filteredImages.length === 0) return null;

    return (
      <div className="space-y-3 mb-4">
        {filteredImages.map((img: any) => (
          <div key={img.id} className="border rounded-lg p-3 bg-slate-50 dark:bg-slate-800/50">
            <img
              src={buildImageUrl(img.url)}
              alt={img.alt_text || img.file_name}
              className={`rounded-lg ${
                img.display_width === "full" ? "w-full" :
                img.display_width === "large" ? "max-w-3xl mx-auto" :
                img.display_width === "medium" ? "max-w-xl mx-auto" :
                "max-w-md mx-auto"
              }`}
            />
            {img.caption && (
              <p className="text-sm text-slate-600 dark:text-slate-400 mt-2 text-center italic">
                {img.caption}
              </p>
            )}
          </div>
        ))}
      </div>
    );
  };

  const renderQuestionIcon = (type: string) => {
    switch (type) {
      case "ESSAY":
        return <FileText className="w-5 h-5" />;
      case "FILE_UPLOAD":
        return <Upload className="w-5 h-5" />;
      default:
        return <MessageSquare className="w-5 h-5" />;
    }
  };

  const getQuestionTypeName = (type: string) => {
    const typeMap: Record<string, string> = {
      SINGLE_CHOICE: "Chọn một đáp án",
      MULTIPLE_CHOICE: "Chọn nhiều đáp án",
      SHORT_ANSWER: "Trả lời ngắn",
      ESSAY: "Tự luận",
      FILE_UPLOAD: "Nộp file",
      FILL_BLANK_TEXT: "Điền vào chỗ trống",
      FILL_BLANK_DROPDOWN: "Chọn từ dropdown",
    };
    return typeMap[type] || type;
  };

  const renderChoiceQuestion = (qa: QuestionWithAnswer) => {
    const { question, student_answer } = qa;
    const studentChoices = student_answer?.answer_data?.selected_option_ids || 
                           (student_answer?.answer_data?.selected_option_id ? [student_answer.answer_data.selected_option_id] : []);

    return (
      <div className="space-y-2">
        {question.answer_options
          .sort((a, b) => a.order_index - b.order_index)
          .map((option) => {
            const isStudentChoice = studentChoices.includes(option.id);
            const isCorrect = option.is_correct;
            
            let bgColor = "bg-white";
            let borderColor = "border-slate-200 dark:border-slate-700";
            let iconColor = "text-slate-400 dark:text-slate-600";
            let icon: ReactNode = null;

            if (isStudentChoice && isCorrect) {
              // Student chose correct answer
              bgColor = "bg-green-50";
              borderColor = "border-green-300";
              iconColor = "text-green-600";
              icon = <CheckCircle className="w-5 h-5" />;
            } else if (isStudentChoice && !isCorrect) {
              // Student chose wrong answer
              bgColor = "bg-red-50";
              borderColor = "border-red-300";
              iconColor = "text-red-600";
              icon = <XCircle className="w-5 h-5" />;
            } else if (!isStudentChoice && isCorrect && review?.show_correct_answers) {
              // Show correct answer that student didn't choose
              bgColor = "bg-green-50";
              borderColor = "border-green-200";
              iconColor = "text-green-500";
              icon = <CheckCircle className="w-5 h-5" />;
            }

            return (
              <div
                key={option.id}
                className={`flex items-start gap-3 p-4 border-2 rounded-lg ${bgColor} ${borderColor}`}
              >
                <div className={iconColor}>{icon || <div className="w-5 h-5" />}</div>
                <div className="flex-1">
                  <p className="text-slate-800 dark:text-slate-200">{option.option_text}</p>
                  {isStudentChoice && !isCorrect && review?.show_correct_answers && (
                    <p className="text-xs text-red-600 mt-1">✗ Đáp án bạn đã chọn</p>
                  )}
                  {!isStudentChoice && isCorrect && review?.show_correct_answers && (
                    <p className="text-xs text-green-600 mt-1">✓ Đáp án đúng</p>
                  )}
                </div>
              </div>
            );
          })}
      </div>
    );
  };

  const renderShortAnswerQuestion = (qa: QuestionWithAnswer) => {
    const { question, student_answer } = qa;
    const studentAnswerText = student_answer?.answer_data?.answer_text || "";

    return (
      <div className="space-y-3">
        {/* Student's answer */}
        <div className="bg-slate-50 dark:bg-slate-800/50 border-2 border-slate-200 dark:border-slate-700 rounded-lg p-4">
          <p className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">Câu trả lời của bạn:</p>
          {studentAnswerText ? (
            <p className="text-slate-800 dark:text-slate-200 font-medium">{studentAnswerText}</p>
          ) : (
            <p className="text-slate-400 dark:text-slate-600 italic">Chưa trả lời</p>
          )}
        </div>

        {/* Correct answers (if show_correct_answers) */}
        {review?.show_correct_answers && question.correct_answers?.length > 0 && (
          <div className="bg-green-50 border-2 border-green-200 rounded-lg p-4">
            <p className="text-sm font-medium text-green-800 mb-2">
              Đáp án chấp nhận:
            </p>
            <ul className="space-y-1">
              {question.correct_answers.map((ans) => (
                <li key={ans.id} className="text-green-800 flex items-start gap-2">
                  <CheckCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
                  <span>
                    {ans.answer_text}
                    {ans.case_sensitive && <span className="text-xs ml-2">(Phân biệt hoa thường)</span>}
                    {ans.exact_match && <span className="text-xs ml-2">(Khớp chính xác)</span>}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Grader feedback */}
        {student_answer?.grader_feedback && (
          <div className="bg-blue-50 border-2 border-blue-200 rounded-lg p-4">
            <p className="text-sm font-medium text-blue-800 mb-2 flex items-center gap-2">
              <MessageSquare className="w-4 h-4" />
              Nhận xét của giáo viên:
            </p>
            <p className="text-blue-900">{student_answer.grader_feedback}</p>
          </div>
        )}
      </div>
    );
  };

  const renderEssayQuestion = (qa: QuestionWithAnswer) => {
    const { student_answer } = qa;
    const essayText = student_answer?.answer_data?.text || 
                     student_answer?.answer_data?.answer_text || "";

    return (
      <div className="space-y-3">
        {/* Student's essay */}
        <div className="bg-slate-50 dark:bg-slate-800/50 border-2 border-slate-200 dark:border-slate-700 rounded-lg p-4">
          <p className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">Bài làm của bạn:</p>
          {essayText ? (
            <p className="text-slate-800 dark:text-slate-200 whitespace-pre-wrap">{essayText}</p>
          ) : (
            <p className="text-slate-400 dark:text-slate-600 italic">Chưa trả lời</p>
          )}
        </div>

        {/* Grader feedback */}
        {student_answer?.grader_feedback && (
          <div className="bg-blue-50 border-2 border-blue-200 rounded-lg p-4">
            <p className="text-sm font-medium text-blue-800 mb-2 flex items-center gap-2">
              <MessageSquare className="w-4 h-4" />
              Nhận xét của giáo viên:
            </p>
            <p className="text-blue-900 whitespace-pre-wrap">{student_answer.grader_feedback}</p>
          </div>
        )}
      </div>
    );
  };

  const renderFileUploadQuestion = (qa: QuestionWithAnswer) => {
    const { student_answer } = qa;
    const fileName = student_answer?.answer_data?.file_name || "";
    const filePath = student_answer?.answer_data?.file_path || "";

    return (
      <div className="space-y-3">
        {/* Student's file */}
        <div className="bg-slate-50 dark:bg-slate-800/50 border-2 border-slate-200 dark:border-slate-700 rounded-lg p-4">
          <p className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">File bạn đã nộp:</p>
          {fileName ? (
            <div className="flex items-center gap-3">
              <Upload className="w-5 h-5 text-blue-600" />
              <div className="flex-1">
                <p className="text-slate-800 dark:text-slate-200 font-medium">{fileName}</p>
                {filePath && (
                  <a
                    href={`/files/${filePath}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-600 hover:underline text-sm"
                  >
                    Tải xuống file →
                  </a>
                )}
              </div>
            </div>
          ) : (
            <p className="text-slate-400 dark:text-slate-600 italic">Chưa nộp file</p>
          )}
        </div>

        {/* Grader feedback */}
        {student_answer?.grader_feedback && (
          <div className="bg-blue-50 border-2 border-blue-200 rounded-lg p-4">
            <p className="text-sm font-medium text-blue-800 mb-2 flex items-center gap-2">
              <MessageSquare className="w-4 h-4" />
              Nhận xét của giáo viên:
            </p>
            <p className="text-blue-900">{student_answer.grader_feedback}</p>
          </div>
        )}
      </div>
    );
  };

  const renderFillBlankTextQuestion = (qa: QuestionWithAnswer) => {
    const { question, student_answer } = qa;
    
    // Parse settings
    const settings: FillBlankTextSettings = question.settings || { blank_count: 0, blanks: [] };
    
    // Parse correct answers
    const correctAnswers: FillBlankTextCorrectAnswer[] = question.correct_answers.map(ca => ({
      blank_id: ca.blank_id || 0,
      answer_text: ca.answer_text,
      case_sensitive: ca.case_sensitive,
      exact_match: ca.exact_match,
    }));
    
    // Parse student answer
    const studentAnswerData: FillBlankTextStudentAnswer = student_answer?.answer_data || { blanks: [] };

    return (
      <div className="space-y-3">
        <FillBlankTextStudent
          questionText={question.question_text}
          settings={settings}
          value={studentAnswerData}
          onChange={() => {}} // Read-only in review mode
          disabled={true}
          showCorrectAnswers={review?.show_correct_answers || false}
          correctAnswers={correctAnswers}
        />

        {/* Grader feedback */}
        {student_answer?.grader_feedback && (
          <div className="bg-blue-50 border-2 border-blue-200 rounded-lg p-4 mt-4">
            <p className="text-sm font-medium text-blue-800 mb-2 flex items-center gap-2">
              <MessageSquare className="w-4 h-4" />
              Nhận xét của giáo viên:
            </p>
            <p className="text-blue-900">{student_answer.grader_feedback}</p>
          </div>
        )}
      </div>
    );
  };

  const renderFillBlankDropdownQuestion = (qa: QuestionWithAnswer) => {
    const { question, student_answer } = qa;
    
    // Parse settings
    const settings: FillBlankDropdownSettings = question.settings || { blank_count: 0, blanks: [] };
    
    // Parse options
    const options: FillBlankDropdownOption[] = question.answer_options.map(opt => ({
      id: opt.id,
      blank_id: opt.blank_id || 0,
      option_text: opt.option_text,
      is_correct: opt.is_correct,
      order_index: opt.order_index,
    }));
    
    // Parse student answer
    const studentAnswerData: FillBlankDropdownStudentAnswer = student_answer?.answer_data || { blanks: [] };

    return (
      <div className="space-y-3">
        <FillBlankDropdownStudent
          questionText={question.question_text}
          settings={settings}
          options={options}
          value={studentAnswerData}
          onChange={() => {}} // Read-only in review mode
          disabled={true}
          showCorrectAnswers={review?.show_correct_answers || false}
          studentAnswer={studentAnswerData}
        />

        {/* Grader feedback */}
        {student_answer?.grader_feedback && (
          <div className="bg-blue-50 border-2 border-blue-200 rounded-lg p-4 mt-4">
            <p className="text-sm font-medium text-blue-800 mb-2 flex items-center gap-2">
              <MessageSquare className="w-4 h-4" />
              Nhận xét của giáo viên:
            </p>
            <p className="text-blue-900">{student_answer.grader_feedback}</p>
          </div>
        )}
      </div>
    );
  };

  const renderQuestionAnswer = (qa: QuestionWithAnswer) => {
    const { question } = qa;

    switch (question.question_type) {
      case "SINGLE_CHOICE":
      case "MULTIPLE_CHOICE":
        return renderChoiceQuestion(qa);
      case "SHORT_ANSWER":
        return renderShortAnswerQuestion(qa);
      case "ESSAY":
        return renderEssayQuestion(qa);
      case "FILE_UPLOAD":
        return renderFileUploadQuestion(qa);
      case "FILL_BLANK_TEXT":
        return renderFillBlankTextQuestion(qa);
      case "FILL_BLANK_DROPDOWN":
        return renderFillBlankDropdownQuestion(qa);
      default:
        return (
          <p className="text-slate-500 dark:text-slate-500 italic">
            Loại câu hỏi này chưa được hỗ trợ xem lại
          </p>
        );
    }
  };

  if (loading) {
    return (
      <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
        <div className="bg-white dark:bg-slate-900 rounded-2xl p-8 shadow-2xl">
          <div className="w-10 h-10 border-4 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto"></div>
          <p className="text-center mt-3 text-slate-600 dark:text-slate-400 text-sm font-medium">
            Đang tải bài làm...
          </p>
        </div>
      </div>
    );
  }

  if (error || !review) {
    return (
      <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
        <div className="bg-white dark:bg-slate-900 rounded-2xl max-w-md w-full p-6 shadow-2xl border border-red-200 dark:border-red-900/50">
          <XCircle className="w-10 h-10 text-red-500 mx-auto mb-3" />
          <h3 className="text-lg font-bold text-center text-slate-900 dark:text-slate-50 mb-2">Có lỗi xảy ra</h3>
          <p className="text-center text-slate-600 dark:text-slate-400 text-sm mb-4">
            {error || "Không thể tải bài làm"}
          </p>
          <button
            onClick={onClose}
            className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 rounded-xl transition-all"
          >
            Đóng
          </button>
        </div>
      </div>
    );
  }

  const { attempt, quiz, questions_with_answers, show_correct_answers, show_feedback } = review;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-60 flex items-center justify-center z-50 p-4 overflow-y-auto">
      <div className="bg-white rounded-2xl max-w-5xl w-full my-8 shadow-2xl">
        {/* Header */}
        <div
          className={`p-6 text-white rounded-t-2xl ${
            attempt.is_passed
              ? "bg-gradient-to-r from-green-600 to-emerald-600"
              : "bg-gradient-to-r from-blue-600 to-indigo-600"
          }`}
        >
          <div className="flex items-start justify-between mb-4">
            <div>
              <h2 className="text-2xl font-bold mb-2">{quiz.title}</h2>
              <div className="flex items-center gap-4 text-sm opacity-90">
                <span>Lần làm #{attempt.attempt_number}</span>
                <span>•</span>
                <span className="flex items-center gap-1">
                  <Award className="w-4 h-4" />
                  {attempt.earned_points?.toFixed(1) || 0}/{attempt.total_points} điểm
                </span>
                <span>•</span>
                <span>{attempt.percentage?.toFixed(1) || 0}%</span>
              </div>
            </div>
            <Button
              onClick={onClose}
              className="bg-white bg-opacity-20 hover:bg-opacity-30 border-0"
            >
              Đóng
            </Button>
          </div>

          {/* Info badges */}
          <div className="flex flex-wrap gap-2 mt-4">
            {show_correct_answers && (
              <div className="px-3 py-1 bg-white bg-opacity-20 rounded-full text-xs font-medium flex items-center gap-1">
                <Eye className="w-3 h-3" />
                Hiển thị đáp án đúng
              </div>
            )}
            {show_feedback && (
              <div className="px-3 py-1 bg-white bg-opacity-20 rounded-full text-xs font-medium flex items-center gap-1">
                <MessageSquare className="w-3 h-3" />
                Hiển thị giải thích
              </div>
            )}
          </div>
        </div>

        {/* Questions */}
        <div className="p-6 max-h-[calc(100vh-300px)] overflow-y-auto">
          <div className="space-y-6">
            {questions_with_answers.map((qa, index) => {
              const question = qa.question;
              const studentAnswer = qa.student_answer;
              const isCorrect = studentAnswer?.is_correct ?? false;
              const hasGraded = studentAnswer?.points_earned !== undefined;

              return (
                <div
                  key={question.id}
                  className="border-2 border-slate-200 dark:border-slate-700 rounded-xl overflow-hidden"
                >
                  {/* Question Header */}
                  <div
                    className={`p-4 border-b-2 ${
                      hasGraded
                        ? isCorrect
                          ? "bg-green-50 border-green-200"
                          : question.question_type === "ESSAY" || question.question_type === "SHORT_ANSWER" || question.question_type === "FILE_UPLOAD"
                          ? "bg-yellow-50 border-yellow-200"
                          : "bg-red-50 border-red-200"
                        : "bg-slate-50 dark:bg-slate-800/50 border-slate-200 dark:border-slate-700"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex items-start gap-3 flex-1">
                        <div
                          className={`w-8 h-8 rounded-lg flex items-center justify-center text-white font-bold text-sm ${
                            hasGraded
                              ? isCorrect
                                ? "bg-green-600"
                                : question.question_type === "ESSAY" || question.question_type === "SHORT_ANSWER" || question.question_type === "FILE_UPLOAD"
                                ? "bg-yellow-600"
                                : "bg-red-600"
                              : "bg-slate-400 dark:bg-slate-600"
                          }`}
                        >
                          {index + 1}
                        </div>
                        <div className="flex-1">
                          <div className="flex items-center gap-2 mb-2">
                            {renderQuestionIcon(question.question_type)}
                            <span className="text-xs px-2 py-1 bg-white border rounded-full">
                              {getQuestionTypeName(question.question_type)}
                            </span>
                            {hasGraded && (
                              <span
                                className={`text-xs px-2 py-1 rounded-full font-medium ${
                                  isCorrect
                                    ? "bg-green-100 text-green-800"
                                    : question.question_type === "ESSAY" || question.question_type === "SHORT_ANSWER" || question.question_type === "FILE_UPLOAD"
                                    ? "bg-yellow-100 text-yellow-800"
                                    : "bg-red-100 text-red-800"
                                }`}
                              >
                                {isCorrect ? "✓ Đúng" : question.question_type === "ESSAY" || question.question_type === "SHORT_ANSWER" || question.question_type === "FILE_UPLOAD" ? "Đã được chấm" :"✗ Sai"}
                              </span>
                            )}
                            {!hasGraded && (
                              <span className="text-xs px-2 py-1 bg-yellow-100 text-yellow-800 rounded-full font-medium flex items-center gap-1">
                                <AlertCircle className="w-3 h-3" />
                                Chưa chấm
                              </span>
                            )}
                          </div>
                          {/* For fill blank questions, don't show question_text here as it's already in the component */}
                          {question.question_type !== "FILL_BLANK_TEXT" && 
                           question.question_type !== "FILL_BLANK_DROPDOWN" && (
                            <p className="text-slate-900 dark:text-slate-50 font-medium mb-1">
                              {question.question_text}
                            </p>
                          )}
                          <div className="flex items-center gap-4 text-sm text-slate-600 dark:text-slate-400">
                            <span className="flex items-center gap-1">
                              <Award className="w-4 h-4" />
                              {studentAnswer?.points_earned?.toFixed(1) || 0}/{question.points} điểm
                            </span>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Question Body */}
                  <div className="p-4">
                    {renderQuestionImages(question, "top")}
                    
                    {renderQuestionAnswer(qa)}

                    {renderQuestionImages(question, "bottom")}

                    {/* Explanation */}
                    {show_feedback && question.explanation && (
                      <div className="mt-4 bg-amber-50 border-2 border-amber-200 rounded-lg p-4">
                        <p className="text-sm font-medium text-amber-800 mb-2 flex items-center gap-2">
                          <MessageSquare className="w-4 h-4" />
                          Giải thích:
                        </p>
                        <p className="text-amber-900">{question.explanation}</p>
                      </div>
                    )}
                    {!isCorrect && (
                      <button
                        onClick={() => setDiagnosisTarget({ qId: question.id, text: question.question_text })}
                        className="mt-3 flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold bg-violet-50 dark:bg-violet-950/30 text-violet-700 dark:text-violet-300 border border-violet-200 dark:border-violet-800 rounded-lg hover:bg-violet-100 dark:hover:bg-violet-950/50 transition-colors">
                        <Sparkles className="w-3.5 h-3.5" />
                        AI Phân tích lỗi này
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
          {diagnosisTarget && (
            <AIDiagnosisModal
              attemptId={attemptId}
              questionId={diagnosisTarget.qId}
              questionText={diagnosisTarget.text}
              onClose={() => setDiagnosisTarget(null)}
            />
          )}
        </div>

        {/* Footer */}
        <div className="p-6 bg-slate-50 dark:bg-slate-800/50 border-t rounded-b-2xl">
          <div className="flex items-center justify-between">
            <p className="text-sm text-slate-600 dark:text-slate-400">
              Bạn đã hoàn thành bài quiz này
            </p>
            <Button
              onClick={onClose}
              className="bg-blue-600 hover:bg-blue-700 text-white"
            >
              Đóng
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}