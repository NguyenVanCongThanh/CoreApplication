import { Task } from "./task";

// ─── Announcement ───────────────────────────────────────────────────────────

export type Announcement = {
  id: number;
  title: string;
  content: string;
  images: string[];
  status: "PENDING" | "APPROVED" | "DENIED" | "EXPIRED";
  createdAt?: string;
  updatedAt?: string;
  createdBy?: string;
};

export interface AnnouncementItem {
  id: number;
  title: string;
  content: string;
  type: "INFO" | "WARNING" | "URGENT";
  target: "ALL" | "STUDENT" | "LECTURER";
  createdAt: string;
}

export const ANNOUNCEMENT_STATUSES = ["PENDING", "APPROVED", "DENIED", "EXPIRED"];

export const STATUS_COLORS = {
  PENDING: "bg-yellow-100 text-yellow-800 border-yellow-300",
  IN_PROGRESS: "bg-blue-100 text-blue-800 border-blue-300",
  COMPLETED: "bg-green-100 text-green-800 border-green-300",
  POSTPONED: "bg-gray-100 text-gray-800 border-gray-300",
  APPROVED: "bg-green-100 text-green-800 border-green-300",
  DENIED: "bg-red-100 text-red-800 border-red-300",
  EXPIRED: "bg-gray-100 text-gray-800 border-gray-300",
};

// ─── Event ───────────────────────────────────────────────────────────────────

export type EventItem = {
  id: number;
  title: string;
  description: string;
  statusEvent: "PENDING" | "IN_PROGRESS" | "COMPLETED" | "POSTPONED";
  startTime?: string;
  endTime?: string;
  capacity?: number;
  createdAt?: string;
  updatedAt?: string;
  tasks?: Task[];
};

export type MockEvent = {
  id: number | string;
  text: string;
  start: string;
  end: string;
  backColor?: string;
  participants?: string[];
  ownerId?: string;
  tasks?: Task[];
};

export const EVENT_STATUSES = ["PENDING", "IN_PROGRESS", "COMPLETED", "POSTPONED"] as const;
