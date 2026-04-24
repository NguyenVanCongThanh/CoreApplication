"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogTrigger,
} from "@/components/ui/dialog";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import type { LlmModel, LlmProvider } from "@/services/llmConfigService";
import { llmConfigService } from "@/services/llmConfigService";

type Props = {
  models: LlmModel[];
  providers: LlmProvider[];
  onChanged: () => void;
};

export function ModelsPanel({ models, providers, onChanged }: Props) {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">Models</h2>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Mỗi provider có nhiều model. Context window, giá token, default temperature đều chỉnh được live.
          </p>
        </div>
        <ModelDialog providers={providers} onSaved={onChanged} />
      </div>

      <div className="overflow-hidden rounded-lg border border-slate-200 dark:border-slate-800">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 dark:bg-slate-900/60 text-slate-500 text-xs uppercase">
            <tr>
              <th className="px-4 py-2 text-left">Provider</th>
              <th className="px-4 py-2 text-left">Model</th>
              <th className="px-4 py-2 text-right">Ctx</th>
              <th className="px-4 py-2 text-left">Capabilities</th>
              <th className="px-4 py-2 text-right">Giá in/out (/1K)</th>
              <th className="px-4 py-2 text-center">Bật</th>
              <th className="px-4 py-2" />
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
            {models.map((m) => (
              <ModelRow key={m.id} model={m} providers={providers} onChanged={onChanged} />
            ))}
            {models.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-slate-400">
                  Chưa có model nào.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ModelRow({
  model, providers, onChanged,
}: {
  model: LlmModel;
  providers: LlmProvider[];
  onChanged: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [open, setOpen] = useState(false);

  const toggle = async () => {
    setBusy(true);
    try {
      await llmConfigService.updateModel(model.id, { enabled: !model.enabled });
      onChanged();
    } finally {
      setBusy(false);
    }
  };
  const remove = async () => {
    if (!confirm(`Xoá model "${model.model_name}"? Các binding tới model này sẽ bị xoá.`)) return;
    setBusy(true);
    try {
      await llmConfigService.deleteModel(model.id);
      onChanged();
    } finally {
      setBusy(false);
    }
  };

  const caps: string[] = [];
  if (model.supports_tools) caps.push("tools");
  if (model.supports_json) caps.push("json");
  if (model.supports_streaming) caps.push("stream");
  if (model.supports_vision) caps.push("vision");

  return (
    <tr className="hover:bg-slate-50 dark:hover:bg-slate-900/40">
      <td className="px-4 py-3 font-mono text-xs">{model.provider_code}</td>
      <td className="px-4 py-3">
        <div className="font-medium">{model.display_name || model.model_name}</div>
        <div className="text-xs text-slate-500 font-mono">{model.model_name}</div>
      </td>
      <td className="px-4 py-3 text-right tabular-nums">{model.context_window.toLocaleString()}</td>
      <td className="px-4 py-3">
        <div className="flex flex-wrap gap-1">
          {caps.map((c) => (
            <span key={c} className="rounded bg-slate-100 dark:bg-slate-800 px-1.5 py-0.5 text-[10px]">
              {c}
            </span>
          ))}
        </div>
      </td>
      <td className="px-4 py-3 text-right text-xs tabular-nums">
        ${model.input_cost_per_1k.toFixed(5)} / ${model.output_cost_per_1k.toFixed(5)}
      </td>
      <td className="px-4 py-3 text-center">
        <button
          disabled={busy}
          onClick={toggle}
          className={`inline-flex h-6 w-11 items-center rounded-full transition-colors ${
            model.enabled ? "bg-emerald-500" : "bg-slate-300 dark:bg-slate-700"
          } disabled:opacity-50`}
        >
          <span
            className={`inline-block h-5 w-5 transform rounded-full bg-white transition ${
              model.enabled ? "translate-x-5" : "translate-x-0.5"
            }`}
          />
        </button>
      </td>
      <td className="px-4 py-3 text-right">
        <div className="flex justify-end gap-2">
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
              <Button variant="outline" size="sm">Sửa</Button>
            </DialogTrigger>
            <ModelDialogContent
              model={model}
              providers={providers}
              onSaved={() => {
                setOpen(false);
                onChanged();
              }}
            />
          </Dialog>
          <Button variant="destructive" size="sm" onClick={remove} disabled={busy}>Xoá</Button>
        </div>
      </td>
    </tr>
  );
}

function ModelDialog({
  providers, onSaved,
}: {
  providers: LlmProvider[];
  onSaved: () => void;
}) {
  const [open, setOpen] = useState(false);
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button disabled={providers.length === 0}>+ Thêm model</Button>
      </DialogTrigger>
      <ModelDialogContent
        providers={providers}
        onSaved={() => {
          setOpen(false);
          onSaved();
        }}
      />
    </Dialog>
  );
}

function ModelDialogContent({
  model, providers, onSaved,
}: {
  model?: LlmModel;
  providers: LlmProvider[];
  onSaved: () => void;
}) {
  const [providerId, setProviderId] = useState<string>(
    model ? String(model.provider_id) : providers[0]?.id ? String(providers[0].id) : ""
  );
  const [modelName, setModelName] = useState(model?.model_name ?? "");
  const [displayName, setDisplayName] = useState(model?.display_name ?? "");
  const [family, setFamily] = useState(model?.family ?? "");
  const [contextWindow, setContextWindow] = useState(String(model?.context_window ?? 8192));
  const [temperature, setTemperature] = useState(String(model?.default_temperature ?? 0.3));
  const [maxTokens, setMaxTokens] = useState(String(model?.default_max_tokens ?? 1024));
  const [inCost, setInCost] = useState(String(model?.input_cost_per_1k ?? 0));
  const [outCost, setOutCost] = useState(String(model?.output_cost_per_1k ?? 0));
  const [supportsJson, setSupportsJson] = useState(model?.supports_json ?? true);
  const [supportsTools, setSupportsTools] = useState(model?.supports_tools ?? false);
  const [supportsStreaming, setSupportsStreaming] = useState(model?.supports_streaming ?? true);
  const [supportsVision, setSupportsVision] = useState(model?.supports_vision ?? false);
  const [enabled, setEnabled] = useState(model?.enabled ?? true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const save = async () => {
    setSaving(true);
    setError(null);
    try {
      if (model) {
        await llmConfigService.updateModel(model.id, {
          model_name: modelName, display_name: displayName || null, family: family || null,
          context_window: Number(contextWindow),
          default_temperature: Number(temperature), default_max_tokens: Number(maxTokens),
          input_cost_per_1k: Number(inCost), output_cost_per_1k: Number(outCost),
          supports_json: supportsJson, supports_tools: supportsTools,
          supports_streaming: supportsStreaming, supports_vision: supportsVision, enabled,
        });
      } else {
        await llmConfigService.upsertModel({
          provider_id: Number(providerId), model_name: modelName,
          display_name: displayName || null, family: family || null,
          context_window: Number(contextWindow),
          default_temperature: Number(temperature), default_max_tokens: Number(maxTokens),
          input_cost_per_1k: Number(inCost), output_cost_per_1k: Number(outCost),
          supports_json: supportsJson, supports_tools: supportsTools,
          supports_streaming: supportsStreaming, supports_vision: supportsVision, enabled,
        });
      }
      onSaved();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <DialogContent className="max-w-lg">
      <DialogHeader>
        <DialogTitle>{model ? "Sửa model" : "Thêm model"}</DialogTitle>
      </DialogHeader>

      <div className="grid grid-cols-2 gap-3">
        <div className="col-span-2">
          <Label>Provider</Label>
          <Select value={providerId} onValueChange={setProviderId} disabled={!!model}>
            <SelectTrigger><SelectValue placeholder="Chọn provider" /></SelectTrigger>
            <SelectContent>
              {providers.map((p) => (
                <SelectItem key={p.id} value={String(p.id)}>{p.code}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="col-span-2">
          <Label>Model name</Label>
          <Input value={modelName} onChange={(e) => setModelName(e.target.value)}
                 placeholder="llama-3.3-70b-versatile" />
        </div>
        <div>
          <Label>Display name</Label>
          <Input value={displayName} onChange={(e) => setDisplayName(e.target.value)} />
        </div>
        <div>
          <Label>Family</Label>
          <Input value={family} onChange={(e) => setFamily(e.target.value)} placeholder="llama / claude / gemini" />
        </div>
        <div>
          <Label>Context window</Label>
          <Input type="number" value={contextWindow} onChange={(e) => setContextWindow(e.target.value)} />
        </div>
        <div>
          <Label>Default temperature</Label>
          <Input type="number" step="0.01" value={temperature} onChange={(e) => setTemperature(e.target.value)} />
        </div>
        <div>
          <Label>Default max_tokens</Label>
          <Input type="number" value={maxTokens} onChange={(e) => setMaxTokens(e.target.value)} />
        </div>
        <div>
          <Label>Input $/1K</Label>
          <Input type="number" step="0.00001" value={inCost} onChange={(e) => setInCost(e.target.value)} />
        </div>
        <div>
          <Label>Output $/1K</Label>
          <Input type="number" step="0.00001" value={outCost} onChange={(e) => setOutCost(e.target.value)} />
        </div>
        <div className="col-span-2 flex flex-wrap gap-4 pt-1 text-sm">
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={supportsJson} onChange={(e) => setSupportsJson(e.target.checked)} />
            supports_json
          </label>
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={supportsTools} onChange={(e) => setSupportsTools(e.target.checked)} />
            supports_tools
          </label>
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={supportsStreaming} onChange={(e) => setSupportsStreaming(e.target.checked)} />
            supports_streaming
          </label>
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={supportsVision} onChange={(e) => setSupportsVision(e.target.checked)} />
            supports_vision
          </label>
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />
            enabled
          </label>
        </div>
        {error && <p className="col-span-2 text-sm text-rose-600">{error}</p>}
      </div>

      <DialogFooter>
        <Button onClick={save} disabled={saving || !modelName || !providerId}>
          {saving ? "Đang lưu…" : "Lưu"}
        </Button>
      </DialogFooter>
    </DialogContent>
  );
}