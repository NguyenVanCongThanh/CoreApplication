import { DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";

type ModalFooterProps = {
  onOpenChange: (open: boolean) => void;
  onSave: () => void;
};

export default function ModalFooter({
  onOpenChange,
  onSave,
}: ModalFooterProps) {
  return (
    <DialogFooter className="pt-4 border-t border-slate-100 dark:border-slate-800 gap-2">
      <Button
        variant="outline"
        onClick={() => onOpenChange(false)}
        className="border border-slate-300 dark:border-slate-700
                   text-slate-700 dark:text-slate-300
                   hover:bg-slate-50 dark:hover:bg-slate-800
                   rounded-xl px-5 font-medium transition-all duration-200 active:scale-95"
      >
        Hủy
      </Button>

      <Button
        onClick={onSave}
        className="bg-blue-600 hover:bg-blue-700 text-white font-semibold
                   px-6 rounded-xl shadow-sm transition-all duration-200 active:scale-95"
      >
        Lưu sự kiện
      </Button>
    </DialogFooter>
  );
}
