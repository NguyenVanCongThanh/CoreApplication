import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { INPUT_BASE, LABEL_BASE } from "../../../../constants/modalStyles";
import { EVENT_STATUSES, STATUS_COLORS } from "@/types";

function StatusField({ value, isViewMode, onChange }: any) {
  return (
    <div className="space-y-1.5">
      <Label className={LABEL_BASE}>Trạng thái</Label>
      {!isViewMode ? (
        <Select value={value || "PENDING"} onValueChange={onChange}>
          <SelectTrigger className="rounded-xl border border-slate-300 dark:border-slate-700">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {EVENT_STATUSES.map((status) => (
              <SelectItem key={status} value={status}>
                <span className={STATUS_COLORS[status as any]}>{status}</span>
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      ) : (
        <span className={STATUS_COLORS[value as any]}>{value}</span>
      )}
    </div>
  );
}

export default StatusField;
