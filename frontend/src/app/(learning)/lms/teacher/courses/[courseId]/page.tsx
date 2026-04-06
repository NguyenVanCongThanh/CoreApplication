import { redirect } from "next/navigation";

/**
 * /lms/teacher/courses/[courseId]
 *
 * Immediately redirects to the overview sub-page so that the
 * [courseId]/layout.tsx can correctly identify the active tab.
 */
export default function CourseDetailRoot({
  params,
}: {
  params: { courseId: string };
}) {
  redirect(`/lms/teacher/courses/${params.courseId}/overview`);
}
