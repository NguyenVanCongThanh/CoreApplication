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
import { Badge } from "@/components/ui/badge";
import { Calendar, Clock, ListTodo, ExternalLink } from "lucide-react";
import { EventItem, ModalMode, EVENT_STATUSES, STATUS_COLORS, PRIORITY_COLORS } from "@/types";

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
  
  const titleText = {
    add: "✨ Tạo Sự Kiện Mới",
    edit: "✏️ Chỉnh Sửa Sự Kiện",
    view: "👁️ Xem Sự Kiện",
  };

  const getPriorityColor = (priority: string) => {
    return PRIORITY_COLORS[priority as keyof typeof PRIORITY_COLORS] || "bg-gray-100 text-gray-800";
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto bg-gradient-to-br from-slate-50 to-purple-50 border-2 border-purple-200/50 shadow-2xl">
        <DialogHeader>
          <DialogTitle className="text-2xl font-bold bg-gradient-to-r from-purple-600 to-pink-600 bg-clip-text text-transparent">
            {titleText[mode]}
          </DialogTitle>
        </DialogHeader>
        
        <div className="space-y-5">
          {/* Event Information Section */}
          <div className="bg-white rounded-xl p-5 shadow-sm border border-gray-100">
            <h3 className="text-lg font-semibold text-gray-800 mb-4 flex items-center gap-2">
              <Calendar className="h-5 w-5 text-purple-600" />
              Thông Tin Sự Kiện
            </h3>
            
            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="title" className="text-sm font-semibold text-gray-700">
                  Tên Sự Kiện
                </Label>
                <Input
                  id="title"
                  value={event.title || ""}
                  onChange={(e) => onChange({ ...event, title: e.target.value })}
                  disabled={isViewMode}
                  className="border-2 border-gray-200 focus:border-purple-400 rounded-xl transition-all"
                  placeholder="Nhập tên sự kiện..."
                  autoFocus={false}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="description" className="text-sm font-semibold text-gray-700">
                  Mô Tả
                </Label>
                <Textarea
                  id="description"
                  value={event.description || ""}
                  onChange={(e) => onChange({ ...event, description: e.target.value })}
                  disabled={isViewMode}
                  className="border-2 border-gray-200 focus:border-purple-400 rounded-xl min-h-[100px] transition-all"
                  placeholder="Mô tả chi tiết về sự kiện..."
                  autoFocus={false}
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="startTime" className="text-sm font-semibold text-gray-700">
                    Ngày Bắt Đầu
                  </Label>
                  {!isViewMode ? (
                    <Input
                      id="startTime"
                      type="datetime-local"
                      value={event.startTime || ""}
                      onChange={(e) => onChange({ ...event, startTime: e.target.value })}
                      className="border-2 border-gray-200 focus:border-purple-400 rounded-xl transition-all"
                      autoFocus={false}
                    />
                  ) : (
                    <div className="text-sm text-gray-600 flex items-center gap-2 bg-gray-50 rounded-lg p-2">
                      <Clock className="h-4 w-4 text-purple-600" />
                      {event.startTime ? new Date(event.startTime).toLocaleString('vi-VN') : 'Chưa xác định'}
                    </div>
                  )}
                </div>

                <div className="space-y-2">
                  <Label htmlFor="endTime" className="text-sm font-semibold text-gray-700">
                    Ngày Kết Thúc
                  </Label>
                  {!isViewMode ? (
                    <Input
                      id="endTime"
                      type="datetime-local"
                      value={event.endTime || ""}
                      onChange={(e) => onChange({ ...event, endTime: e.target.value })}
                      className="border-2 border-gray-200 focus:border-purple-400 rounded-xl transition-all"
                      autoFocus={false}
                    />
                  ) : (
                    <div className="text-sm text-gray-600 flex items-center gap-2 bg-gray-50 rounded-lg p-2">
                      <Clock className="h-4 w-4 text-purple-600" />
                      {event.endTime ? new Date(event.endTime).toLocaleString('vi-VN') : 'Chưa xác định'}
                    </div>
                  )}
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="capacity" className="text-sm font-semibold text-gray-700">
                    Số Lượng Người Tham Gia
                  </Label>
                  {!isViewMode ? (
                    <Input
                      id="capacity"
                      type="number"
                      value={event.capacity || ""}
                      onChange={(e) => onChange({ ...event, capacity: Number(e.target.value) })}
                      className="border-2 border-gray-200 focus:border-purple-400 rounded-xl transition-all"
                      placeholder="Nhập số lượng tối đa..."
                      min={0}
                      autoFocus={false}
                    />
                  ) : (
                    <div className="text-sm text-gray-600 bg-gray-50 rounded-lg p-2">
                      {event.capacity ? `${event.capacity} người` : 'Không giới hạn'}
                    </div>
                  )}
                </div>

                <div className="space-y-2">
                  <Label htmlFor="statusEvent" className="text-sm font-semibold text-gray-700">
                    Trạng Thái
                  </Label>
                  {!isViewMode ? (
                    <Select
                      value={event.statusEvent || "PENDING"}
                      onValueChange={(value) => onChange({ ...event, statusEvent: value as any })}
                    >
                      <SelectTrigger className="border-2 border-gray-200 focus:border-purple-400 rounded-xl">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {EVENT_STATUSES.map(status => (
                          <SelectItem key={status} value={status}>
                            <span className={`px-3 py-1 rounded-full text-xs font-medium ${STATUS_COLORS[status as keyof typeof STATUS_COLORS]}`}>
                              {status}
                            </span>
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  ) : (
                    <div>
                      <Badge className={`${STATUS_COLORS[event.statusEvent as keyof typeof STATUS_COLORS]} text-sm`}>
                        {event.statusEvent}
                      </Badge>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Tasks Section - Only show in view mode */}
          {isViewMode && event.tasks && event.tasks.length > 0 && (
            <div className="bg-white rounded-xl p-5 shadow-sm border border-gray-100">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-gray-800 flex items-center gap-2">
                  <ListTodo className="h-5 w-5 text-purple-600" />
                  Danh Sách Tasks ({event.tasks.length})
                </h3>
                <Button
                  variant="outline"
                  size="sm"
                  className="text-purple-600 border-purple-300 hover:bg-purple-50"
                  onClick={() => window.location.href = `/events/${event.id}/tasks`}
                >
                  <ExternalLink className="h-4 w-4 mr-1" />
                  Xem Chi Tiết
                </Button>
              </div>
              
              <div className="space-y-3 max-h-[400px] overflow-y-auto">
                {event.tasks.map((task: any) => (
                  <div
                    key={task.id}
                    className="border border-gray-200 rounded-lg p-4 hover:shadow-md transition-all bg-gradient-to-r from-white to-gray-50"
                  >
                    <div className="flex items-start justify-between mb-2">
                      <h4 className="font-semibold text-gray-800 flex-1">{task.title}</h4>
                      <div className="flex gap-2">
                        {task.priority && (
                          <Badge className={`${getPriorityColor(task.priority)} text-xs`}>
                            {task.priority}
                          </Badge>
                        )}
                        {task.columnId && (
                          <Badge variant="outline" className="text-xs">
                            {task.columnId}
                          </Badge>
                        )}
                      </div>
                    </div>
                    
                    {task.description && (
                      <p className="text-sm text-gray-600 mb-2 line-clamp-2">
                        {task.description}
                      </p>
                    )}
                    
                    {(task.startDate || task.endDate) && (
                      <div className="flex gap-4 text-xs text-gray-500 mt-2">
                        {task.startDate && (
                          <div className="flex items-center gap-1">
                            <Clock className="h-3 w-3" />
                            <span>Bắt đầu: {new Date(task.startDate).toLocaleDateString('vi-VN')}</span>
                          </div>
                        )}
                        {task.endDate && (
                          <div className="flex items-center gap-1">
                            <Clock className="h-3 w-3" />
                            <span>Kết thúc: {new Date(task.endDate).toLocaleDateString('vi-VN')}</span>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {isViewMode && (!event.tasks || event.tasks.length === 0) && (
            <div className="bg-white rounded-xl p-5 shadow-sm border border-gray-100">
              <div className="text-center py-8 text-gray-500">
                <ListTodo className="h-12 w-12 mx-auto mb-3 text-gray-300" />
                <p>Chưa có task nào cho sự kiện này</p>
              </div>
            </div>
          )}
        </div>

        {!isViewMode && (
          <DialogFooter>
            <Button 
              onClick={onSave}
              className="bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 text-white font-semibold px-6 rounded-xl shadow-lg hover:shadow-xl transition-all"
            >
              💾 Lưu Sự Kiện
            </Button>
          </DialogFooter>
        )}
      </DialogContent>
    </Dialog>
  );
}