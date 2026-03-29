import { Badge } from "@/components/ui/badge";
import { Field, FieldLabel } from "@/components/ui/field";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { EVENT_STATUS_MAP } from "@/constants/event";
import { cn } from "@/lib/utils";

function StatusField({ value, isViewMode, onChange }: any) {
  const statusKey = value || "PENDING";
  const statusConfig =
    EVENT_STATUS_MAP[statusKey as keyof typeof EVENT_STATUS_MAP];

  return (
    <Field>
      <FieldLabel>Trạng thái</FieldLabel>
      {!isViewMode ? (
        <Select value={statusKey} onValueChange={(v) => onChange(v as any)}>
          <SelectTrigger className="rounded-xl bg-slate-50 dark:bg-slate-800 border-slate-300 dark:border-slate-700">
            <SelectValue>
              <Badge
                variant="outline"
                className={cn(
                  "border-transparent shadow-none",
                  statusConfig?.style,
                )}
              >
                {statusConfig?.label}
              </Badge>
            </SelectValue>
          </SelectTrigger>
          <SelectContent className="rounded-xl">
            {Object.entries(EVENT_STATUS_MAP).map(([key, info]) => (
              <SelectItem key={key} value={key}>
                <Badge
                  variant="outline"
                  className={cn(
                    "px-2 py-0.5 border-transparent shadow-none",
                    info.style,
                  )}
                >
                  {info.label}
                </Badge>
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      ) : (
        <div className="pt-1">
          <Badge
            variant="outline"
            className={cn(
              "px-3 py-1 rounded-lg text-sm font-semibold border-transparent shadow-none",
              statusConfig?.style,
            )}
          >
            {statusConfig?.label}
          </Badge>
        </div>
      )}
    </Field>
  );
}

export default StatusField;
