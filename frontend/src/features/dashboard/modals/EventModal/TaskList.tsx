import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Clock, ListTodo, ExternalLink } from "lucide-react";
import { PRIORITY_COLORS } from "@/types";
import { SECTION_LABEL } from "../../../../constants/modalStyles";

type Props = {
  tasks?: any[];
  eventId?: string | number;
};

export default function TaskList({ tasks, eventId }: Props) {
  const hasTasks = (tasks?.length ?? 0) > 0;

  return (
    <section>
      <div className="flex items-center justify-between mb-3">
        <p className={`${SECTION_LABEL} flex items-center gap-1.5`}>
          <ListTodo className="h-3.5 w-3.5" />
          Tasks ({tasks?.length ?? 0})
        </p>

        {hasTasks && (
          <Button
            variant="outline"
            size="sm"
            onClick={() => (window.location.href = `/events/${eventId}/tasks`)}
            className="border border-slate-300 dark:border-slate-700
                       text-slate-600 dark:text-slate-400
                       hover:bg-slate-50 dark:hover:bg-slate-800
                       rounded-lg text-xs font-medium transition-all duration-200"
          >
            <ExternalLink className="h-3.5 w-3.5 mr-1" />
            Xem chi tiết
          </Button>
        )}
      </div>

      {hasTasks ? (
        <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
          {tasks!.map((task: any) => (
            <div
              key={task.id}
              className="rounded-xl p-3.5
                         bg-slate-50 dark:bg-slate-800
                         border border-slate-200 dark:border-slate-700
                         hover:border-blue-200 dark:hover:border-blue-800
                         hover:bg-blue-50/30 dark:hover:bg-blue-950/20
                         transition-all duration-200"
            >
              <div className="flex items-start justify-between mb-1.5">
                <h4
                  className="font-semibold text-sm text-slate-800 dark:text-slate-100
                             flex-1 pr-2"
                >
                  {task.title}
                </h4>

                <div className="flex gap-1.5 flex-shrink-0">
                  {task.priority && (
                    <Badge
                      className={`${
                        PRIORITY_COLORS[
                          task.priority as keyof typeof PRIORITY_COLORS
                        ] || "bg-slate-100 text-slate-600"
                      } text-xs border-0`}
                    >
                      {task.priority}
                    </Badge>
                  )}

                  {task.columnId && (
                    <Badge
                      variant="outline"
                      className="text-xs text-slate-500 dark:text-slate-400
                                 border-slate-300 dark:border-slate-600"
                    >
                      {task.columnId}
                    </Badge>
                  )}
                </div>
              </div>

              {task.description && (
                <p
                  className="text-xs text-slate-500 dark:text-slate-400
                             leading-relaxed line-clamp-2 mb-2"
                >
                  {task.description}
                </p>
              )}

              {(task.startDate || task.endDate) && (
                <div className="flex gap-4 text-xs text-slate-400 dark:text-slate-500 mt-1">
                  {task.startDate && (
                    <span className="flex items-center gap-1">
                      <Clock className="h-3 w-3" />
                      {new Date(task.startDate).toLocaleDateString("vi-VN")}
                    </span>
                  )}

                  {task.endDate && (
                    <span className="flex items-center gap-1">
                      <Clock className="h-3 w-3" />
                      {new Date(task.endDate).toLocaleDateString("vi-VN")}
                    </span>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      ) : (
        <div
          className="flex flex-col items-center justify-center py-8 rounded-xl
                     bg-slate-50 dark:bg-slate-800
                     border border-slate-200 dark:border-slate-700"
        >
          <ListTodo className="h-8 w-8 text-slate-300 dark:text-slate-600 mb-2" />
          <p className="text-sm text-slate-400 dark:text-slate-500">
            Chưa có task nào cho sự kiện này
          </p>
        </div>
      )}
    </section>
  );
}
