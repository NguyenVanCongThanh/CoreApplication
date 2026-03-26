import { ROLES, TYPE_TAGS, TEAMS } from "@/constants/user";

export type ModalMode = "add" | "edit" | "view";

export type UserLogin = {
  id: number | string;
  name: string;
  email: string;
  role: (typeof ROLES)[number] | string;
};

export type User = {
  id: number | string;
  name: string;
  code: string;
  email: string;
  team: (typeof TEAMS)[number] | string;
  type: (typeof TYPE_TAGS)[number] | string;
  role: (typeof ROLES)[number] | string;
  score?: number;
  totalScore?: number;
  dateAdded?: string;
  status?: boolean;
  active?: boolean;
  profilePicture?: string;
};
