export type TaskLink = {
  id: number | string;
  url: string;
  title: string;
};

export type TaskScore = {
  id?: number;
  taskId?: number;
  taskTitle?: string;
  userId?: number;
  userName?: string;
  userEmail?: string;
  userCode?: string;
  score: number;
  applied?: boolean;
  scoredById?: number;
  scoredByName?: string;
  scoredAt?: string;
  appliedAt?: string;
  notes?: string;
};

export type Task = {
  id: number | string;
  title: string;
  description: string;
  priority?: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
  assignees: (number | string)[];
  links: TaskLink[];
  startDate?: string;
  endDate?: string;
  columnId: string;
  eventId?: number | string;
  event?: {
    id: number;
    title: string;
  };
  createdAt?: string;
  createdBy?: {
    id: number;
    name: string;
    email: string;
  };
  updatedAt?: string;
  updatedBy?: {
    id: number;
    name: string;
    email: string;
  };
};

export type Column = {
  id: string;
  title: string;
  color: string;
  tasks: Task[];
};

export interface TaskInfo {
  id: number;
  title: string;
  description?: string;
  priority?: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
  columnId?: string;
  startDate?: string;
  endDate?: string;
}

export const PRIORITY_COLORS = {
  LOW: "bg-gray-100 text-gray-800 border-gray-300",
  MEDIUM: "bg-blue-100 text-blue-800 border-blue-300",
  HIGH: "bg-orange-100 text-orange-800 border-orange-300",
  CRITICAL: "bg-red-100 text-red-800 border-red-300",
};
