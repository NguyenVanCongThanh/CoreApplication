"use client";

import { useParams } from "next/navigation";
import QuizReviewModal from "@/components/lms/student/QuizReviewModal";

export default function AttemptResultPage() {
  const params = useParams();
  const attemptId = parseInt(params.attemptId as string);

  return (
    <QuizReviewModal
      attemptId={attemptId}
      onBack={() => window.history.back()}
    />
  );
}