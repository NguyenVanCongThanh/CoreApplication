"use client";

import React from "react";
import { format } from "date-fns";
import { vi } from "date-fns/locale";
import { Calendar as CalendarIcon, Clock, Users } from "lucide-react";

import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Calendar } from "@/components/ui/calendar";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

import { EventItem, EVENT_STATUSES, STATUS_COLORS } from "@/types";
import { INPUT_BASE, LABEL_BASE } from "../../../../constants/modalStyles";
import TaskList from "./TaskList";
import TimeField from "./TimeField";

type Props = {
  isViewMode: boolean;
  event: Partial<EventItem>;
  onChange: (event: Partial<EventItem>) => void;
};

export default function ModalForm({ isViewMode, event, onChange }: Props) {
  const formatDateDisplay = (dateStr?: string) => {
    if (!dateStr) return "Chọn ngày...";
    return format(new Date(dateStr), "PPP HH:mm", { locale: vi });
  };

  // Helper để cập nhật ngày nhưng giữ nguyên giờ phút hiện tại (hoặc mặc định)
  const handleDateChange = (
    field: "startTime" | "endTime",
    selectedDate: Date | undefined,
  ) => {
    if (!selectedDate) return;

    // Nếu đã có giá trị cũ, giữ lại giờ/phút. Nếu chưa có, mặc định 00:00
    const currentDate = event[field]
      ? new Date(event[field] as string)
      : new Date();
    selectedDate.setHours(currentDate.getHours());
    selectedDate.setMinutes(currentDate.getMinutes());

    onChange({ ...event, [field]: selectedDate.toISOString() });
  };

  return (
    <div className="space-y-6 py-2">
      <section className="space-y-4">
        {/* Title & Description giữ nguyên ... */}
        <div className="space-y-1.5">
          <Label className={LABEL_BASE}>Tên sự kiện</Label>
          <Input
            value={event.title ?? ""}
            onChange={(e) => onChange({ ...event, title: e.target.value })}
            disabled={isViewMode}
            placeholder="Nhập tên sự kiện..."
            className={INPUT_BASE}
          />
        </div>

        <div className="space-y-1.5">
          <Label className={LABEL_BASE}>Mô tả</Label>
          <Textarea
            value={event.description ?? ""}
            onChange={(e) =>
              onChange({ ...event, description: e.target.value })
            }
            disabled={isViewMode}
            placeholder="Mô tả chi tiết về sự kiện..."
            rows={3}
            className={`${INPUT_BASE} resize-none`}
          />
        </div>

        {/* Time - Sử dụng Popover + Calendar tách biệt Giờ/Phút */}
        <div className="grid grid-cols-1 gap-6">
          <TimeField
            label="Ngày bắt đầu"
            value={event.startTime}
            disabled={isViewMode}
            INPUT_BASE={INPUT_BASE}
            LABEL_BASE={LABEL_BASE}
            onChange={(val) => onChange({ ...event, startTime: val })}
          />

          <TimeField
            label="Ngày kết thúc"
            value={event.endTime}
            disabled={isViewMode}
            INPUT_BASE={INPUT_BASE}
            LABEL_BASE={LABEL_BASE}
            onChange={(val) => onChange({ ...event, endTime: val })}
          />
        </div>

        {/* Capacity & Status giữ nguyên ... */}
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-1.5">
            <Label className={LABEL_BASE}>Số người tham gia</Label>
            {!isViewMode ? (
              <Input
                type="number"
                value={event.capacity ?? ""}
                onChange={(e) =>
                  onChange({
                    ...event,
                    capacity:
                      e.target.value === ""
                        ? undefined
                        : Number(e.target.value),
                  })
                }
                placeholder="Không giới hạn"
                min={0}
                className={INPUT_BASE}
              />
            ) : (
              <div className="flex items-center gap-2 rounded-xl p-3 text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300">
                <Users className="h-4 w-4 text-blue-600 dark:text-blue-400 flex-shrink-0" />
                <span>
                  {event.capacity
                    ? `${event.capacity} người`
                    : "Không giới hạn"}
                </span>
              </div>
            )}
          </div>

          <div className="space-y-1.5">
            <Label className={LABEL_BASE}>Trạng thái</Label>
            {!isViewMode ? (
              <Select
                value={event.statusEvent ?? "PENDING"}
                onValueChange={(v) =>
                  onChange({ ...event, statusEvent: v as any })
                }
              >
                <SelectTrigger className="rounded-xl bg-slate-50 dark:bg-slate-800 border-slate-300 dark:border-slate-700">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="rounded-xl">
                  {EVENT_STATUSES.map((status) => (
                    <SelectItem key={status} value={status}>
                      <span
                        className={`px-2 py-0.5 rounded-md text-xs font-medium ${STATUS_COLORS[status as keyof typeof STATUS_COLORS]}`}
                      >
                        {status}
                      </span>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            ) : (
              <span
                className={`inline-block px-3 py-1 rounded-lg text-sm font-semibold ${STATUS_COLORS[event.statusEvent as keyof typeof STATUS_COLORS]}`}
              >
                {event.statusEvent}
              </span>
            )}
          </div>
        </div>
      </section>

      {isViewMode && <TaskList tasks={event.tasks} eventId={event.id} />}
    </div>
  );
}
