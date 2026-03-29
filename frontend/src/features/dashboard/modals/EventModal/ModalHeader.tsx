import { DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { ModalMode } from "@/types/user";

const TITLE_MAP = {
  add: "Tạo sự kiện mới",
  edit: "Chỉnh sửa sự kiện",
  view: "Chi tiết sự kiện",
};

const ModalHeader = ({ mode }: { mode: ModalMode }) => {
  return (
    <DialogHeader className="pb-4 border-b border-slate-100 dark:border-slate-800">
      <DialogTitle className="text-2xl font-bold text-slate-900 dark:text-slate-50">
        {TITLE_MAP[mode]}
      </DialogTitle>
    </DialogHeader>
  );
};

export default ModalHeader;
