"use client";

/**
 * StudyPlanWidget — renders a personalized study plan from the mentor agent.
 */
import { cn } from "@/lib/utils";
import { BookOpen, CheckCircle } from "lucide-react";

interface StudyItem {
  topic: string;
  reason?: string;
  priority?: "high" | "medium" | "low";
  mastery?: number;
}

interface StudyPlanWidgetProps {
  props: {
    items: StudyItem[];
    title?: string;
  };
}

const PRIORITY_STYLES: Record<string, string> = {
  high: "border-l-red-500",
  medium: "border-l-yellow-500",
  low: "border-l-green-500",
};

export function StudyPlanWidget({ props }: StudyPlanWidgetProps) {
  const { items, title } = props;

  if (!items || items.length === 0) return null;

  return (
    <div className="space-y-3">
      <div className="text-xs font-semibold text-blue-600 dark:text-blue-400 uppercase tracking-wider">
        {title || "Kế hoạch học tập"}
      </div>

      <div className="space-y-2">
        {items.map((item, i) => (
          <div
            key={i}
            className={cn(
              "flex items-start gap-3 p-3 rounded-xl",
              "bg-white dark:bg-slate-900",
              "border border-slate-200 dark:border-slate-800",
              "border-l-4",
              PRIORITY_STYLES[item.priority || "medium"],
            )}
          >
            <div className="w-6 h-6 rounded-full bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center flex-shrink-0 mt-0.5">
              <span className="text-xs font-bold text-blue-600 dark:text-blue-400">
                {i + 1}
              </span>
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-slate-800 dark:text-slate-200">
                {item.topic}
              </p>
              {item.reason && (
                <p className="text-xs text-slate-500 dark:text-slate-500 mt-0.5">
                  {item.reason}
                </p>
              )}
            </div>
            {item.mastery !== undefined && (
              <span className="text-xs text-slate-400 flex-shrink-0">
                {Math.round(item.mastery * 100)}%
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
