"use client";

import React from "react";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { EventItem, ModalMode } from "@/types";
import EventHeader from "./EventHeader";
import EventFooter from "./EventFooter";
import EventForm from "./EventForm/EventForm";

interface EventModalProps {
  open: boolean;
  mode: ModalMode;
  event: Partial<EventItem>;
  onOpenChange: (open: boolean) => void;
  onChange: (event: Partial<EventItem>) => void;
  onSave: () => void;
}

export function EventModal({
  open,
  mode,
  event,
  onOpenChange,
  onChange,
  onSave,
}: EventModalProps) {
  const isViewMode = mode === "view";
  // const formatDate = (d?: string) =>
  //   d ? new Date(d).toLocaleString("vi-VN") : "Chưa xác định";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="max-w-2xl max-h-[90vh] overflow-y-auto
                                bg-white dark:bg-slate-900
                                border border-slate-200 dark:border-slate-800
                                shadow-xl rounded-2xl"
      >
        <EventHeader mode={mode} />
        <EventForm isViewMode={isViewMode} event={event} onChange={onChange} />
        {!isViewMode && (
          <EventFooter
            onOpenChange={() => onOpenChange(false)}
            onSave={() => {
              onSave();
              onOpenChange(false);
            }}
          />
        )}
      </DialogContent>
    </Dialog>
  );
}
