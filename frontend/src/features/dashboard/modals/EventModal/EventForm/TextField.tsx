import { Label } from "@/components/ui/label";
import { INPUT_BASE, LABEL_BASE } from "@/constants/modalStyles";

function TextField({
  label,
  value,
  disabled,
  onChange,
}: {
  label: string;
  value: string;
  disabled?: boolean;
  onChange: (v: string) => void;
}) {
  return (
    <div className="space-y-1.5">
      <Label className={LABEL_BASE}>{label}</Label>
      <input
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value)}
        className={INPUT_BASE}
      />
    </div>
  );
}

export default TextField;
