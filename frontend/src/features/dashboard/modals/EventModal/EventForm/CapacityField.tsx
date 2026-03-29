"use client";

import React from "react";
import { Users } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Field, FieldLabel } from "@/components/ui/field";

interface CapacityFieldProps {
  value?: number;
  isViewMode: boolean;
  onChange: (val: number | undefined) => void;
}

export function CapacityField({
  value,
  isViewMode,
  onChange,
}: CapacityFieldProps) {
  return (
    <Field>
      <FieldLabel>Số người tham gia</FieldLabel>
      {!isViewMode ? (
        <Input
          type="number"
          value={value ?? ""}
          onChange={(e) =>
            onChange(e.target.value === "" ? undefined : Number(e.target.value))
          }
          placeholder="Không giới hạn"
          min={0}
          className="rounded-xl"
        />
      ) : (
        <div className="flex items-center gap-2 rounded-xl p-2.5 text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300">
          <Users className="h-4 w-4 text-blue-600 dark:text-blue-400 flex-shrink-0" />
          <span>{value ? `${value} người` : "Không giới hạn"}</span>
        </div>
      )}
    </Field>
  );
}

export default CapacityField;
