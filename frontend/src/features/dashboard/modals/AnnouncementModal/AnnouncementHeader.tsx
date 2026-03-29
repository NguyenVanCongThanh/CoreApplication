import {
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ModalMode } from "@/types/user";
import { ANNOUNCEMENT_TITLE_MAP } from "@/constants/announcement";

export function AnnouncementHeader({ mode }: { mode: ModalMode }) {
  return (
    <DialogHeader className="pb-4 border-b border-slate-100 dark:border-slate-800">
      <DialogTitle className="text-2xl font-bold text-slate-900 dark:text-slate-50">
        {ANNOUNCEMENT_TITLE_MAP[mode].title}
      </DialogTitle>
      <DialogDescription className="text-sm text-slate-500 dark:text-slate-400 mt-1">
        {ANNOUNCEMENT_TITLE_MAP[mode].description}
      </DialogDescription>
    </DialogHeader>
  );
}
