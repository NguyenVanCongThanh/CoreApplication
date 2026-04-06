"use client";

import { useParams } from "next/navigation";
import { AIQuizGenPanel } from "@/components/lms/teacher/page/AIQuizGenPanel";
import { AIHeatmapSection } from "@/components/lms/AIHeatmapSection";

/**
 * /lms/teacher/courses/[courseId]/ai
 *
 * Two AI features on one page:
 *   1. AIQuizGenPanel  – knowledge node management + quiz generation + draft review
 *   2. AIHeatmapSection – class-level knowledge-gap heatmap
 */
export default function CourseAIPage() {
  const { courseId } = useParams<{ courseId: string }>();
  const id = Number(courseId);

  return (
    <div className="space-y-8">
      {/* Quiz generation + knowledge nodes */}
      <AIQuizGenPanel courseId={id} />

      {/* Class heatmap */}
      <div className="border-t border-slate-200 dark:border-slate-800 pt-8">
        <AIHeatmapSection courseId={id} role="teacher" />
      </div>
    </div>
  );
}
