"use client";

import React from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Bell, Eye, Edit, Trash2 } from "lucide-react";
import { ANNOUNCEMENT_STATUS_MAP } from "@/constants/announcement";
import SafeImage from "@/components/common/SafeImage";
import { cn } from "@/lib/utils";
import { Announcement } from "@/types";

interface AnnouncementCardProps {
  announcement: Announcement;
  isAdmin: boolean;
  onView: () => void;
  onEdit: () => void;
  onDelete: () => void;
}

export function AnnouncementCard({
  announcement,
  isAdmin,
  onView,
  onEdit,
  onDelete,
}: AnnouncementCardProps) {
  // Lấy config từ MAP, fallback về PENDING nếu không tìm thấy
  const statusConfig =
    ANNOUNCEMENT_STATUS_MAP[
      announcement.status as keyof typeof ANNOUNCEMENT_STATUS_MAP
    ] || ANNOUNCEMENT_STATUS_MAP.PENDING;

  return (
    <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm hover:shadow-md hover:-translate-y-0.5 transition-all duration-300 overflow-hidden group flex flex-col h-full">
      {/* Thumbnail */}
      <div className="relative w-full h-44 flex-shrink-0 overflow-hidden bg-slate-100 dark:bg-slate-800">
        {announcement.images?.[0] ? (
          <SafeImage
            src={announcement.images[0]}
            alt={announcement.title}
            fill
            className="object-cover group-hover:scale-105 transition-transform duration-500"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <Bell className="h-12 w-12 text-slate-300 dark:text-slate-600" />
          </div>
        )}

        {/* Status Badge - Sử dụng MAP và Badge shadcn */}
        <div className="absolute top-3 right-3">
          <Badge
            variant="secondary"
            className={cn(
              "font-semibold border shadow-sm px-2.5 py-0.5 rounded-lg backdrop-blur-sm",
              statusConfig.style,
            )}
          >
            {statusConfig.label}
          </Badge>
        </div>
      </div>

      {/* Content */}
      <div className="p-4 flex flex-col flex-1">
        <h3 className="text-lg font-bold text-slate-800 dark:text-slate-100 mb-1.5 line-clamp-2 group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors duration-200">
          {announcement.title}
        </h3>
        <p className="text-sm text-slate-500 dark:text-slate-400 line-clamp-3 leading-relaxed flex-1">
          {announcement.content}
        </p>

        {/* Actions */}
        <div className="flex items-center gap-1.5 pt-3 mt-3 border-t border-slate-100 dark:border-slate-800">
          <Button
            size="sm"
            variant="ghost"
            onClick={onView}
            className="flex-1 h-8 text-slate-600 dark:text-slate-400 hover:text-blue-600 dark:hover:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-950/40 rounded-lg text-xs font-medium transition-all"
          >
            <Eye className="h-3.5 w-3.5 mr-1" />
            Xem
          </Button>

          {isAdmin && (
            <>
              <Button
                size="sm"
                variant="ghost"
                onClick={onEdit}
                title="Chỉnh sửa"
                className="h-8 w-8 p-0 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-all"
              >
                <Edit className="h-3.5 w-3.5" />
              </Button>
              <Button
                size="sm"
                variant="ghost"
                onClick={onDelete}
                title="Xóa"
                className="h-8 w-8 p-0 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-all"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </Button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}