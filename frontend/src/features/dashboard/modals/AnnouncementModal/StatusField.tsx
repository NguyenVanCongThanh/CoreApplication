// StatusField.tsx
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ANNOUNCEMENT_STATUSES, STATUS_COLORS } from "@/types";

export function StatusField({
  value,
  isViewMode,
  onChange,
}: {
  value?: string;
  isViewMode: boolean;
  onChange: (v: string) => void;
}) {
  if (isViewMode) {
    return (
      <span
        className={`inline-block px-3 py-1 rounded-lg text-sm font-semibold
        ${STATUS_COLORS[value as keyof typeof STATUS_COLORS]}`}
      >
        {value}
      </span>
    );
  }

  return (
    <Select value={value || "PENDING"} onValueChange={onChange}>
      <SelectTrigger
        className="rounded-xl
                                          border border-slate-300 dark:border-slate-700
                                          bg-slate-50 dark:bg-slate-800
                                          text-slate-900 dark:text-slate-100
                                          focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
      >
        <SelectValue />
      </SelectTrigger>
      <SelectContent
        className="bg-white dark:bg-slate-900
                                          border border-slate-200 dark:border-slate-800 rounded-xl"
      >
        {ANNOUNCEMENT_STATUSES.map((status) => (
          <SelectItem
            key={status}
            value={status}
            className="focus:bg-slate-100 dark:focus:bg-slate-800"
          >
            <span
              className={`px-2 py-0.5 rounded-md text-xs font-medium
                                                    ${STATUS_COLORS[status as keyof typeof STATUS_COLORS]}`}
            >
              {status}
            </span>
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
