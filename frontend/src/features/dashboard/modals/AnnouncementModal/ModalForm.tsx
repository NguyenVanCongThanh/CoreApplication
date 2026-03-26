import { Label } from "@/components/ui/label";
import { Announcement } from "@/types";
import { INPUT_BASE, LABEL_BASE } from "../../../../constants/modalStyles";
import { StatusField } from "./StatusField";
import { ANNOUNCEMENT_STATUSES } from "@/types/announcement-event";
import { ImageField } from "./ImageField";
import { STATUS_COLORS } from "@/types/announcement-event";

export function ModalForm({
  announcement,
  onChange,
  isViewMode,
}: {
  announcement: Partial<Announcement>;
  onChange: (a: Partial<Announcement>) => void;
  isViewMode: boolean;
}) {
  return (
    <div className="space-y-4 py-2">
      {/* Title */}
      <div className="space-y-1.5">
        <Label className={LABEL_BASE}>Tiêu đề</Label>
        <input
          value={announcement.title || ""}
          onChange={(e) => onChange({ ...announcement, title: e.target.value })}
          disabled={isViewMode}
          placeholder="Nhập tiêu đề thông báo..."
          className={INPUT_BASE}
        />
      </div>

      {/* Content */}
      <div className="space-y-1.5">
        <Label className={LABEL_BASE}>Nội dung</Label>
        <textarea
          value={announcement.content || ""}
          onChange={(e) =>
            onChange({ ...announcement, content: e.target.value })
          }
          disabled={isViewMode}
          placeholder="Nhập nội dung chi tiết..."
          rows={4}
          className={`${INPUT_BASE} resize-none`}
        />
      </div>
      {/* Images */}
      <ImageField
        value={announcement.images}
        disabled={isViewMode}
        onChange={(images) => onChange({ ...announcement, images })}
      />

      {/* Status */}
      <div className="space-y-1.5">
        <Label className={LABEL_BASE}>Trạng thái</Label>
        {!isViewMode ? (
          <StatusField
            value={announcement.status}
            isViewMode={isViewMode}
            onChange={(v) =>
              onChange({
                ...announcement,
                status: v as (typeof ANNOUNCEMENT_STATUSES)[number],
              })
            }
          />
        ) : (
          <span
            className={`inline-block px-3 py-1 rounded-lg text-sm font-semibold
                                      ${STATUS_COLORS[announcement.status as keyof typeof STATUS_COLORS]}`}
          >
            {announcement.status}
          </span>
        )}
      </div>
    </div>
  );
}
