import { Label } from "@/components/ui/label";
import { INPUT_BASE, LABEL_BASE } from "../../../../constants/modalStyles";

function TextareaField({ label, value, disabled, onChange }: any) {
  return (
    <div className="space-y-1.5">
      <Label className={LABEL_BASE}>{label}</Label>
      <textarea
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value)}
        rows={3}
        className={`${INPUT_BASE} resize-none`}
      />
    </div>
  );
}

export default TextareaField;
