"use client";

import React from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Announcement, ModalMode, ANNOUNCEMENT_STATUSES, STATUS_COLORS } from "@/types";

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
  
  const titleText = {
    add: "✨ Tạo Thông Báo Mới",
    edit: "✏️ Chỉnh Sửa Thông Báo",
    view: "👁️ Xem Thông Báo",
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl bg-gradient-to-br from-slate-50 to-blue-50 border-2 border-blue-200/50 shadow-2xl">
        <DialogHeader>
          <DialogTitle className="text-2xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
            {titleText[mode]}
          </DialogTitle>
        </DialogHeader>
        
        <div className="space-y-5">
          <div className="space-y-2">
            <Label htmlFor="title" className="text-sm font-semibold text-gray-700">
              Tiêu Đề
            </Label>
            <Input
              id="title"
              value={announcement.title || ""}
              onChange={(e) => onChange({ ...announcement, title: e.target.value })}
              disabled={isViewMode}
              className="border-2 border-gray-200 focus:border-blue-400 rounded-xl transition-all"
              placeholder="Nhập tiêu đề thông báo..."
              autoFocus={false}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="content" className="text-sm font-semibold text-gray-700">
              Nội Dung
            </Label>
            <Textarea
              id="content"
              value={announcement.content || ""}
              onChange={(e) => onChange({ ...announcement, content: e.target.value })}
              disabled={isViewMode}
              className="border-2 border-gray-200 focus:border-blue-400 rounded-xl min-h-[120px] transition-all"
              placeholder="Nhập nội dung chi tiết..."
              autoFocus={false}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="images" className="text-sm font-semibold text-gray-700">
              Hình Ảnh URL (phân cách bởi dấu phẩy)
            </Label>
            <Input
              id="images"
              value={(announcement.images || []).join(", ")}
              onChange={(e) => 
                onChange({ 
                  ...announcement, 
                  images: e.target.value.split(",").map(s => s.trim()).filter(Boolean) 
                })
              }
              disabled={isViewMode}
              className="border-2 border-gray-200 focus:border-blue-400 rounded-xl transition-all"
              placeholder="https://example.com/image1.jpg, https://..."
              autoFocus={false}
            />
          </div>

          {!isViewMode ? (
            <div className="space-y-2">
              <Label htmlFor="status" className="text-sm font-semibold text-gray-700">
                Trạng Thái
              </Label>
              <Select
                value={announcement.status || "PENDING"}
                onValueChange={(value) => onChange({ ...announcement, status: value as any })}
              >
                <SelectTrigger className="border-2 border-gray-200 focus:border-blue-400 rounded-xl">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {ANNOUNCEMENT_STATUSES.map(status => (
                    <SelectItem key={status} value={status}>
                      <span className={`px-3 py-1 rounded-full text-xs font-medium ${STATUS_COLORS[status as keyof typeof STATUS_COLORS]}`}>
                        {status}
                      </span>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          ) : (
            <div className="space-y-2">
              <Label className="text-sm font-semibold text-gray-700">Trạng Thái</Label>
              <div className={`inline-block px-4 py-2 rounded-xl text-sm font-semibold ${STATUS_COLORS[announcement.status as keyof typeof STATUS_COLORS]}`}>
                {announcement.status}
              </div>
            </div>
          )}
        </div>

        {!isViewMode && (
          <DialogFooter>
            <Button 
              onClick={onSave}
              className="bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white font-semibold px-6 rounded-xl shadow-lg hover:shadow-xl transition-all"
            >
              💾 Lưu Thông Báo
            </Button>
          </DialogFooter>
        )}
      </DialogContent>
    </Dialog>
  );
}