"use client";

import React from "react";
import { format } from "date-fns";
import { vi } from "date-fns/locale";
import { Calendar as CalendarIcon } from "lucide-react";

import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Calendar } from "@/components/ui/calendar";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type Props = {
  label: string;
  value?: string;
  onChange: (value: string) => void;
  disabled?: boolean;
  INPUT_BASE: string;
  LABEL_BASE: string;
};

export default function TimeField({
  label,
  value,
  onChange,
  disabled,
  INPUT_BASE,
  LABEL_BASE,
}: Props) {
  const dateObj = value ? new Date(value) : undefined;

  return (
    <div className="space-y-2">
      <Label className={LABEL_BASE}>{label}</Label>

      {!disabled ? (
        <div className="flex gap-2">
          {/* Date */}
          <div className="flex-[2]">
            <Popover>
              <PopoverTrigger asChild>
                <Button
                  variant="outline"
                  className={cn(
                    "w-full justify-start text-left font-normal rounded-xl h-10",
                    !value && "text-muted-foreground",
                    INPUT_BASE,
                  )}
                >
                  <CalendarIcon className="mr-2 h-4 w-4" />
                  {value ? format(dateObj!, "dd/MM/yyyy") : "Chọn ngày..."}
                </Button>
              </PopoverTrigger>

              <PopoverContent className="w-auto p-0 rounded-xl" align="start">
                <Calendar
                  mode="single"
                  selected={dateObj}
                  locale={vi}
                  onSelect={(date) => {
                    if (!date) return;

                    const newDate = date;

                    if (value) {
                      const old = new Date(value);
                      newDate.setHours(old.getHours(), old.getMinutes());
                    } else {
                      newDate.setHours(0, 0, 0, 0);
                    }

                    onChange(newDate.toISOString());
                  }}
                  initialFocus
                />
              </PopoverContent>
            </Popover>
          </div>

          {/* Time */}
          <div className="flex-1 relative">
            <Input
              type="time"
              disabled={!value}
              className={cn(
                INPUT_BASE,
                "h-10 rounded-xl disabled:bg-slate-100 dark:disabled:bg-slate-900",
              )}
              value={value ? format(dateObj!, "HH:mm") : ""}
              onChange={(e) => {
                const [h, m] = e.target.value.split(":");
                const d = new Date(value!);
                d.setHours(parseInt(h), parseInt(m));
                onChange(d.toISOString());
              }}
            />

            {!value && (
              <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                <span className="text-[10px] text-slate-400 uppercase font-bold">
                  Chờ chọn ngày
                </span>
              </div>
            )}
          </div>
        </div>
      ) : (
        <div className="rounded-xl p-3 text-sm bg-slate-50 dark:bg-slate-800 border">
          {value
            ? format(new Date(value), "PPP HH:mm", { locale: vi })
            : "Chưa xác định"}
        </div>
      )}
    </div>
  );
}
