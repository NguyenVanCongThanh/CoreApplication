"use client";

import React from "react";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Announcement, ModalMode } from "@/types";
import { AnnouncementFooter } from "./AnnouncementFooter";
import { AnnouncementForm } from "./AnnouncementForm";
import { AnnouncementHeader } from "./AnnouncementHeader";

interface AnnouncementModalProps {
  open: boolean;
  mode: ModalMode;
  announcement: Partial<Announcement>;
  onOpenChange: (open: boolean) => void;
  onChange: (announcement: Partial<Announcement>) => void;
  onSave: () => void;
}

export function AnnouncementModal({
  open,
  mode,
  announcement,
  onOpenChange,
  onChange,
  onSave,
}: AnnouncementModalProps) {
  const isViewMode = mode === "view";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="max-w-xl
                                bg-white dark:bg-slate-900
                                border border-slate-200 dark:border-slate-800
                                shadow-xl rounded-2xl"
      >
        <AnnouncementHeader mode={mode} />

        <AnnouncementForm
          announcement={announcement}
          onChange={onChange}
          isViewMode={isViewMode}
        />

        {!isViewMode && (
          <AnnouncementFooter
            onCancel={() => onOpenChange(false)}
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
