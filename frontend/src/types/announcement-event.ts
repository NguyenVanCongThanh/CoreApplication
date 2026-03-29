import { Task } from "./task";
import { ANNOUNCEMENT_STATUS_MAP } from "@/constants/announcement";
import { EVENT_STATUS_MAP } from "@/constants/event";

// ─── Announcement ───────────────────────────────────────────────────────────

export type Announcement = {
  id: number;
  title: string;
  content: string;
  images: string[];
  status: Extract<keyof typeof ANNOUNCEMENT_STATUS_MAP, string>;
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

// ─── Event ───────────────────────────────────────────────────────────────────

export type EventItem = {
  id: number;
  title: string;
  description: string;
  // statusEvent: "PENDING" | "IN_PROGRESS" | "COMPLETED" | "POSTPONED";
  statusEvent: Extract<keyof typeof EVENT_STATUS_MAP, string>;
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

// export const EVENT_STATUSES = ["PENDING", "IN_PROGRESS", "COMPLETED", "POSTPONED"] as const;
