import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge"; // Component chuẩn của shadcn
import { ANNOUNCEMENT_STATUS_MAP } from "@/constants/announcement";
import { cn } from "@/lib/utils";

export function StatusField({
  value,
  isViewMode,
  onChange,
}: {
  value?: string;
  isViewMode: boolean;
  onChange: (v: string) => void;
}) {
  const statusKey =
    value && value in ANNOUNCEMENT_STATUS_MAP
      ? (value as keyof typeof ANNOUNCEMENT_STATUS_MAP)
      : "PENDING";

  const config = ANNOUNCEMENT_STATUS_MAP[statusKey];

  // Helper để render Badge đồng nhất
  const renderBadge = (key: keyof typeof ANNOUNCEMENT_STATUS_MAP) => {
    const item = ANNOUNCEMENT_STATUS_MAP[key];
    return (
      <Badge
        variant="outline"
        className={cn("font-medium border-transparent shadow-none", item.style)}
      >
        {item.label}
      </Badge>
    );
  };

  if (isViewMode) {
    return <div className="pt-1">{renderBadge(statusKey)}</div>;
  }

  return (
    <Select value={statusKey} onValueChange={onChange}>
      <SelectTrigger className="w-full rounded-xl border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 h-11 focus:ring-2 focus:ring-blue-500/20">
        <SelectValue>{renderBadge(statusKey)}</SelectValue>
      </SelectTrigger>
      <SelectContent className="bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800 rounded-xl shadow-lg">
        {Object.entries(ANNOUNCEMENT_STATUS_MAP).map(([key, info]) => (
          <SelectItem
            key={key}
            value={key}
            className="focus:bg-slate-100 dark:focus:bg-slate-800 cursor-pointer"
          >
            {renderBadge(key as keyof typeof ANNOUNCEMENT_STATUS_MAP)}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
