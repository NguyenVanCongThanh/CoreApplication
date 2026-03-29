"use client";

import { INPUT_BASE } from "@/constants/modalStyles";
import { FieldLabel } from "@/components/ui/field";

interface ImageFieldProps {
  value?: string[];
  disabled?: boolean;
  onChange: (images: string[]) => void;
}

export function ImageField({
  value = [],
  disabled = false,
  onChange,
}: ImageFieldProps) {
  return (
    <div className="space-y-1.5">
      <FieldLabel>
        Hình ảnh URL
        <span className="text-slate-400 dark:text-slate-600 font-normal ml-1">
          (phân cách bởi dấu phẩy)
        </span>
      </FieldLabel>

      <input
        value={value.join(", ")}
        onChange={(e) => {
          const images = e.target.value
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean);

          onChange(images);
        }}
        disabled={disabled}
        placeholder="https://example.com/image.jpg"
        className={INPUT_BASE}
      />
    </div>
  );
}