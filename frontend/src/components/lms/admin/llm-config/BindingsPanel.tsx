"use client";

import { useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader,
  DialogTitle, DialogTrigger,
} from "@/components/ui/dialog";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import type { LlmBinding, LlmCatalogue, LlmModel } from "@/services/llmConfigService";
import { llmConfigService } from "@/services/llmConfigService";

type Props = {
  bindings: LlmBinding[];
  models: LlmModel[];
  catalogue: LlmCatalogue | null;
  onChanged: () => void;
};

export function BindingsPanel({ bindings, models, catalogue, onChanged }: Props) {
  const byTask = useMemo(() => {
    const m = new Map<string, LlmBinding[]>();
    bindings.forEach((b) => {
      const arr = m.get(b.task_code) ?? [];
      arr.push(b);
      m.set(b.task_code, arr);
    });
    for (const arr of m.values()) arr.sort((a, b) => a.priority - b.priority);
    return m;
  }, [bindings]);

  const allTasks = useMemo(() => {
    const s = new Set<string>(catalogue?.task_codes ?? []);
    bindings.forEach((b) => s.add(b.task_code));
    return Array.from(s).sort();
  }, [catalogue, bindings]);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">Task bindings</h2>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Mỗi task có fallback chain xếp theo priority. Bật <b>Pin</b> để ép gateway chỉ dùng đúng binding này.
          </p>
        </div>
        <BindingDialog models={models} catalogue={catalogue} onSaved={onChanged} />
      </div>

      <div className="space-y-3">
        {allTasks.map((task) => {
          const chain = byTask.get(task) ?? [];
          return (
            <div key={task} className="rounded-lg border border-slate-200 dark:border-slate-800">
              <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900/60 px-4 py-2">
                <div>
                  <code className="text-sm font-mono font-semibold">{task}</code>
                  <span className="ml-2 text-xs text-slate-500">{chain.length} binding(s)</span>
                </div>
                <BindingAddInline task={task} models={models} onSaved={onChanged} />
              </div>

              {chain.length === 0 ? (
                <p className="px-4 py-4 text-sm text-slate-400">Chưa có binding nào.</p>
              ) : (
                <table className="w-full text-sm">
                  <thead className="text-slate-500 text-xs uppercase">
                    <tr>
                      <th className="px-4 py-2 text-left">Priority</th>
                      <th className="px-4 py-2 text-left">Model</th>
                      <th className="px-4 py-2 text-center">JSON</th>
                      <th className="px-4 py-2 text-right">Temp / Max</th>
                      <th className="px-4 py-2 text-center">Pin</th>
                      <th className="px-4 py-2 text-center">Bật</th>
                      <th className="px-4 py-2" />
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
                    {chain.map((b) => (
                      <BindingRow key={b.id} binding={b} onChanged={onChanged} />
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          );
        })}
        {allTasks.length === 0 && (
          <p className="text-center py-12 text-slate-400">Chưa có binding nào.</p>
        )}
      </div>
    </div>
  );
}

function BindingRow({ binding, onChanged }: { binding: LlmBinding; onChanged: () => void }) {
  const [busy, setBusy] = useState(false);

  const patch = async (patch: Parameters<typeof llmConfigService.updateBinding>[1]) => {
    setBusy(true);
    try {
      await llmConfigService.updateBinding(binding.id, patch);
      onChanged();
    } finally {
      setBusy(false);
    }
  };

  const remove = async () => {
    if (!confirm(`Xoá binding ${binding.task_code} → ${binding.model.model_name}?`)) return;
    setBusy(true);
    try {
      await llmConfigService.deleteBinding(binding.id);
      onChanged();
    } finally {
      setBusy(false);
    }
  };

  return (
    <tr className="hover:bg-slate-50 dark:hover:bg-slate-900/40">
      <td className="px-4 py-3 tabular-nums">
        <Input
          type="number"
          className="h-7 w-20"
          value={binding.priority}
          onChange={(e) => patch({ priority: Number(e.target.value) })}
          disabled={busy}
        />
      </td>
      <td className="px-4 py-3">
        <div className="font-mono text-xs">
          {binding.model.provider_code}
          <span className="text-slate-400"> / </span>
          {binding.model.model_name}
        </div>
      </td>
      <td className="px-4 py-3 text-center">
        <input
          type="checkbox"
          checked={binding.json_mode}
          onChange={(e) => patch({ json_mode: e.target.checked })}
          disabled={busy}
        />
      </td>
      <td className="px-4 py-3 text-right text-xs text-slate-500">
        {binding.temperature ?? binding.model.default_temperature} / {binding.max_tokens ?? binding.model.default_max_tokens}
      </td>
      <td className="px-4 py-3 text-center">
        <input
          type="checkbox"
          checked={binding.pinned}
          onChange={(e) => patch({ pinned: e.target.checked })}
          disabled={busy}
        />
      </td>
      <td className="px-4 py-3 text-center">
        <input
          type="checkbox"
          checked={binding.enabled}
          onChange={(e) => patch({ enabled: e.target.checked })}
          disabled={busy}
        />
      </td>
      <td className="px-4 py-3 text-right">
        <Button variant="destructive" size="sm" onClick={remove} disabled={busy}>Xoá</Button>
      </td>
    </tr>
  );
}

function BindingAddInline({
  task, models, onSaved,
}: {
  task: string;
  models: LlmModel[];
  onSaved: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [modelId, setModelId] = useState<string>("");
  const [priority, setPriority] = useState("100");
  const [saving, setSaving] = useState(false);

  const add = async () => {
    if (!modelId) return;
    setSaving(true);
    try {
      await llmConfigService.upsertBinding({
        task_code: task,
        model_id: Number(modelId),
        priority: Number(priority),
      });
      setOpen(false);
      onSaved();
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm" variant="outline">+ Model</Button>
      </DialogTrigger>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle>Thêm model vào chain</DialogTitle>
          <DialogDescription>
            Task: <code className="font-mono">{task}</code>
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div>
            <Label>Model</Label>
            <Select value={modelId} onValueChange={setModelId}>
              <SelectTrigger><SelectValue placeholder="Chọn model" /></SelectTrigger>
              <SelectContent>
                {models.map((m) => (
                  <SelectItem key={m.id} value={String(m.id)}>
                    {m.provider_code} / {m.model_name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label>Priority (thấp hơn = thử trước)</Label>
            <Input type="number" value={priority} onChange={(e) => setPriority(e.target.value)} />
          </div>
        </div>
        <DialogFooter>
          <Button onClick={add} disabled={saving || !modelId}>
            {saving ? "Đang thêm…" : "Thêm"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function BindingDialog({
  models, catalogue, onSaved,
}: {
  models: LlmModel[];
  catalogue: LlmCatalogue | null;
  onSaved: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [taskCode, setTaskCode] = useState<string>(catalogue?.task_codes?.[0] ?? "chat");
  const [customTask, setCustomTask] = useState("");
  const [modelId, setModelId] = useState<string>("");
  const [priority, setPriority] = useState("100");
  const [saving, setSaving] = useState(false);

  const effectiveTask = taskCode === "__custom" ? customTask.trim() : taskCode;

  const save = async () => {
    if (!modelId || !effectiveTask) return;
    setSaving(true);
    try {
      await llmConfigService.upsertBinding({
        task_code: effectiveTask,
        model_id: Number(modelId),
        priority: Number(priority),
      });
      setCustomTask("");
      setModelId("");
      setPriority("100");
      setOpen(false);
      onSaved();
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button disabled={models.length === 0}>+ Thêm binding</Button>
      </DialogTrigger>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Thêm task binding</DialogTitle>
        </DialogHeader>
        <div className="space-y-3">
          <div>
            <Label>Task code</Label>
            <Select value={taskCode} onValueChange={setTaskCode}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                {(catalogue?.task_codes ?? []).map((t) => (
                  <SelectItem key={t} value={t}>{t}</SelectItem>
                ))}
                <SelectItem value="__custom">— Tự định nghĩa —</SelectItem>
              </SelectContent>
            </Select>
            {taskCode === "__custom" && (
              <Input
                className="mt-2"
                value={customTask}
                onChange={(e) => setCustomTask(e.target.value)}
                placeholder="my_custom_task"
              />
            )}
          </div>
          <div>
            <Label>Model</Label>
            <Select value={modelId} onValueChange={setModelId}>
              <SelectTrigger><SelectValue placeholder="Chọn model" /></SelectTrigger>
              <SelectContent>
                {models.map((m) => (
                  <SelectItem key={m.id} value={String(m.id)}>
                    {m.provider_code} / {m.model_name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label>Priority</Label>
            <Input type="number" value={priority} onChange={(e) => setPriority(e.target.value)} />
          </div>
        </div>
        <DialogFooter>
          <Button onClick={save} disabled={saving || !modelId || !effectiveTask}>
            {saving ? "Đang lưu…" : "Lưu"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}