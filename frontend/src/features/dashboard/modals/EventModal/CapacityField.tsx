import { Label } from "@/components/ui/label";
import { INPUT_BASE, LABEL_BASE } from "../../../../constants/modalStyles";
import { Users } from "lucide-react";
import ReadonlyField from "./ReadonlyField";

function CapacityField({ value, isViewMode, onChange }: any) {
  return (
    <div className="space-y-1.5">
      <Label className={LABEL_BASE}>Số người tham gia</Label>
      {!isViewMode ? (
        <input
          type="number"
          value={value || ""}
          onChange={(e) => onChange(Number(e.target.value))}
          className={INPUT_BASE}
        />
      ) : (
        <ReadonlyField
          icon={Users}
          value={value ? `${value} người` : "Không giới hạn"}
        />
      )}
    </div>
  );
}

export default CapacityField;
