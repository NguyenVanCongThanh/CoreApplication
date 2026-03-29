"use client";

import React from "react";
import {
  Field,
  FieldGroup,
  FieldLabel,
  FieldDescription,
} from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Announcement } from "@/types";
import { StatusField } from "./StatusField";
import { ImageField } from "./ImageField";
import { ANNOUNCEMENT_STATUS_MAP } from "@/constants/announcement";

export function AnnouncementForm({
  announcement,
  onChange,
  isViewMode,
}: {
  announcement: Partial<Announcement>;
  onChange: (a: Partial<Announcement>) => void;
  isViewMode: boolean;
}) {
  // Helper để update nhanh các field
  const updateField = (updates: Partial<Announcement>) => {
    onChange({ ...announcement, ...updates });
  };

  return (
    <FieldGroup className="py-2">
      {/* Title */}
      <Field>
        <FieldLabel>Tiêu đề</FieldLabel>
        <Input
          value={announcement.title || ""}
          onChange={(e) => updateField({ title: e.target.value })}
          disabled={isViewMode}
          placeholder="Nhập tiêu đề thông báo..."
          className="rounded-xl"
        />
      </Field>

      {/* Content */}
      <Field>
        <FieldLabel>Nội dung</FieldLabel>
        <Textarea
          value={announcement.content || ""}
          onChange={(e) => updateField({ content: e.target.value })}
          disabled={isViewMode}
          placeholder="Nhập nội dung chi tiết..."
          rows={5}
          className="resize-none rounded-xl"
        />
      </Field>

      {/* Images */}
      <ImageField
        value={announcement.images}
        disabled={isViewMode}
        onChange={(images) => updateField({ images })}
      />
      {!isViewMode && (
        <FieldDescription>
          Hỗ trợ nhiều URL, phân tách bằng dấu phẩy.
        </FieldDescription>
      )}

      {/* Status */}
      <Field>
        <FieldLabel>Trạng thái hiển thị</FieldLabel>
        <StatusField
          value={announcement.status}
          isViewMode={isViewMode}
          onChange={(v) =>
            updateField({ status: v as keyof typeof ANNOUNCEMENT_STATUS_MAP })
          }
        />
      </Field>
    </FieldGroup>
  );
}
