import { Label } from "@/components/ui/label";
import { INPUT_BASE, LABEL_BASE } from "../../../../constants/modalStyles";
import { Clock } from "lucide-react";
import ReadonlyField from "./ReadonlyField";
function DateField({ label, value, isViewMode, onChange }: any) {
  const formatDate = (d?: string) =>
    d ? new Date(d).toLocaleString("vi-VN") : "Chưa xác định";

  return (
    <div className="space-y-1.5">
      <Label className={LABEL_BASE}>{label}</Label>
      {!isViewMode ? (
        <input
          type="datetime-local"
          value={value || ""}
          onChange={(e) => onChange(e.target.value)}
          className={INPUT_BASE}
        />
      ) : (
        <ReadonlyField icon={Clock} value={formatDate(value)} />
      )}
    </div>
  );
}

export default DateField;
