"use client";

import React from "react";
import { Calendar as Users } from "lucide-react";

import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

import { EventItem } from "@/types";
import { EVENT_STATUS_MAP } from "@/constants/event";
import TaskList from "./TaskList";
import TimeField from "./TimeField";
import CapacityField from "./CapacityField";
import StatusField from "./StatusField";

type Props = {
  isViewMode: boolean;
  event: Partial<EventItem>;
  onChange: (event: Partial<EventItem>) => void;
};

export default function EventForm({ isViewMode, event, onChange }: Props) {
  const statusKey = event.statusEvent || "PENDING";
  const statusConfig =
    EVENT_STATUS_MAP[statusKey as keyof typeof EVENT_STATUS_MAP];

  const updateField = (updates: Partial<EventItem>) => {
    onChange({ ...event, ...updates });
  };

  return (
    <div className="space-y-6 py-2">
      <FieldGroup className="space-y-4">
        {/* Tên sự kiện */}
        <Field>
          <FieldLabel>Tên sự kiện</FieldLabel>
          <Input
            value={event.title ?? ""}
            onChange={(e) => updateField({ title: e.target.value })}
            disabled={isViewMode}
            placeholder="Nhập tên sự kiện..."
            className="rounded-xl"
          />
        </Field>

        {/* Mô tả */}
        <Field>
          <FieldLabel>Mô tả</FieldLabel>
          <Textarea
            value={event.description ?? ""}
            onChange={(e) => updateField({ description: e.target.value })}
            disabled={isViewMode}
            placeholder="Mô tả chi tiết về sự kiện..."
            rows={3}
            className="resize-none rounded-xl"
          />
        </Field>

        {/* Thời gian */}
        <FieldGroup className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <TimeField
            label="Ngày bắt đầu"
            value={event.startTime}
            disabled={isViewMode}
            onChange={(val) => updateField({ startTime: val })}
          />

          <TimeField
            label="Ngày kết thúc"
            value={event.endTime}
            disabled={isViewMode}
            onChange={(val) => updateField({ endTime: val })}
          />
        </FieldGroup>

        {/* Số người & Trạng thái */}
        <FieldGroup className="grid grid-cols-2 gap-4">
          <CapacityField
            value={event.capacity}
            isViewMode={isViewMode}
            onChange={(val) => updateField({ capacity: val })}
          />

          <StatusField
            value={event.statusEvent}
            isViewMode={isViewMode}
            onChange={(v) => updateField({ statusEvent: v as any })}
          />
        </FieldGroup>
      </FieldGroup>

      {isViewMode && <TaskList tasks={event.tasks} eventId={event.id} />}
    </div>
  );
}
