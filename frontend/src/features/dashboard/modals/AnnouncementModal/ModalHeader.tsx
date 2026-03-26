import { DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { ModalMode } from "@/types/user";

const TITLE_MAP = {
  add: "Tạo thông báo mới",
  edit: "Chỉnh sửa thông báo",
  view: "Chi tiết thông báo",
};

export function ModalHeader({ mode }: { mode: ModalMode }) {
  return (
    <DialogHeader className="pb-4 border-b border-slate-100 dark:border-slate-800">
      <DialogTitle className="text-2xl font-bold text-slate-900 dark:text-slate-50">
        {TITLE_MAP[mode]}
      </DialogTitle>
    </DialogHeader>
  );
}