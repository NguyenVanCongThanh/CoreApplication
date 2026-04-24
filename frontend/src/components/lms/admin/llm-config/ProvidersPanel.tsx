"use client";

import { useState } from "react";
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
import type { LlmProvider, LlmCatalogue } from "@/services/llmConfigService";
import { llmConfigService } from "@/services/llmConfigService";

type Props = {
  providers: LlmProvider[];
  catalogue: LlmCatalogue | null;
  onChanged: () => void;
};

export function ProvidersPanel({ providers, catalogue, onChanged }: Props) {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">Provider</h2>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Quản lý các nhà cung cấp LLM (Groq, Anthropic, Gemini, Ollama…).
          </p>
        </div>
        <ProviderDialog catalogue={catalogue} onSaved={onChanged} />
      </div>

      <div className="overflow-hidden rounded-lg border border-slate-200 dark:border-slate-800">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 dark:bg-slate-900/60 text-slate-500 text-xs uppercase">
            <tr>
              <th className="px-4 py-2 text-left">Code</th>
              <th className="px-4 py-2 text-left">Tên hiển thị</th>
              <th className="px-4 py-2 text-left">Adapter</th>
              <th className="px-4 py-2 text-left">Base URL</th>
              <th className="px-4 py-2 text-center">Bật</th>
              <th className="px-4 py-2" />
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
            {providers.map((p) => (
              <ProviderRow key={p.id} provider={p} catalogue={catalogue} onChanged={onChanged} />
            ))}
            {providers.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-slate-400">
                  Chưa có provider nào.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ProviderRow({
  provider, catalogue, onChanged,
}: {
  provider: LlmProvider;
  catalogue: LlmCatalogue | null;
  onChanged: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [open, setOpen] = useState(false);

  const toggle = async () => {
    setBusy(true);
    try {
      await llmConfigService.updateProvider(provider.id, { enabled: !provider.enabled });
      onChanged();
    } finally {
      setBusy(false);
    }
  };

  const remove = async () => {
    if (!confirm(`Xoá provider "${provider.code}"? Mọi model + key + binding liên quan sẽ bị xoá theo.`)) return;
    setBusy(true);
    try {
      await llmConfigService.deleteProvider(provider.id);
      onChanged();
    } finally {
      setBusy(false);
    }
  };

  return (
    <tr className="hover:bg-slate-50 dark:hover:bg-slate-900/40">
      <td className="px-4 py-3 font-mono text-xs">{provider.code}</td>
      <td className="px-4 py-3">{provider.display_name}</td>
      <td className="px-4 py-3">
        <code className="rounded bg-slate-100 dark:bg-slate-800 px-1.5 py-0.5 text-xs">
          {provider.adapter_type}
        </code>
      </td>
      <td className="px-4 py-3 text-slate-500 text-xs">{provider.base_url || "—"}</td>
      <td className="px-4 py-3 text-center">
        <button
          disabled={busy}
          onClick={toggle}
          className={`inline-flex h-6 w-11 items-center rounded-full transition-colors ${
            provider.enabled ? "bg-emerald-500" : "bg-slate-300 dark:bg-slate-700"
          } disabled:opacity-50`}
          aria-label="Toggle enabled"
        >
          <span
            className={`inline-block h-5 w-5 transform rounded-full bg-white transition ${
              provider.enabled ? "translate-x-5" : "translate-x-0.5"
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
            <ProviderDialogContent
              provider={provider}
              catalogue={catalogue}
              onSaved={() => {
                setOpen(false);
                onChanged();
              }}
            />
          </Dialog>
          <Button variant="destructive" size="sm" onClick={remove} disabled={busy}>
            Xoá
          </Button>
        </div>
      </td>
    </tr>
  );
}

function ProviderDialog({
  catalogue, onSaved,
}: {
  catalogue: LlmCatalogue | null;
  onSaved: () => void;
}) {
  const [open, setOpen] = useState(false);
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>+ Thêm provider</Button>
      </DialogTrigger>
      <ProviderDialogContent
        catalogue={catalogue}
        onSaved={() => {
          setOpen(false);
          onSaved();
        }}
      />
    </Dialog>
  );
}

function ProviderDialogContent({
  provider, catalogue, onSaved,
}: {
  provider?: LlmProvider;
  catalogue: LlmCatalogue | null;
  onSaved: () => void;
}) {
  const [code, setCode] = useState(provider?.code ?? "");
  const [displayName, setDisplayName] = useState(provider?.display_name ?? "");
  const [adapterType, setAdapterType] = useState(provider?.adapter_type ?? "groq");
  const [baseUrl, setBaseUrl] = useState(provider?.base_url ?? "");
  const [enabled, setEnabled] = useState(provider?.enabled ?? true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const save = async () => {
    setSaving(true);
    setError(null);
    try {
      if (provider) {
        await llmConfigService.updateProvider(provider.id, {
          display_name: displayName,
          adapter_type: adapterType,
          base_url: baseUrl || null,
          enabled,
        });
      } else {
        await llmConfigService.upsertProvider({
          code, display_name: displayName, adapter_type: adapterType,
          base_url: baseUrl || null, enabled,
        });
      }
      onSaved();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  };

  const adapters = catalogue?.adapter_types ?? [];

  return (
    <DialogContent className="max-w-md">
      <DialogHeader>
        <DialogTitle>{provider ? "Sửa provider" : "Thêm provider"}</DialogTitle>
        <DialogDescription>
          Adapter quyết định giao thức gọi API. Base URL dùng cho endpoint tự host (Ollama/vLLM…).
        </DialogDescription>
      </DialogHeader>

      <div className="space-y-3">
        <div>
          <Label>Code</Label>
          <Input
            value={code}
            disabled={!!provider}
            onChange={(e) => setCode(e.target.value.toLowerCase().replace(/\s+/g, "-"))}
            placeholder="groq / anthropic / gemini / ollama-prod"
          />
        </div>
        <div>
          <Label>Tên hiển thị</Label>
          <Input value={displayName} onChange={(e) => setDisplayName(e.target.value)} />
        </div>
        <div>
          <Label>Adapter type</Label>
          <Select value={adapterType} onValueChange={setAdapterType}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {adapters.map((a) => (
                <SelectItem key={a} value={a}>{a}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div>
          <Label>Base URL (tuỳ chọn)</Label>
          <Input
            value={baseUrl ?? ""}
            onChange={(e) => setBaseUrl(e.target.value)}
            placeholder="http://ollama:11434"
          />
        </div>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />
          Bật
        </label>
        {error && <p className="text-sm text-rose-600">{error}</p>}
      </div>

      <DialogFooter>
        <Button onClick={save} disabled={saving || !code || !displayName}>
          {saving ? "Đang lưu…" : "Lưu"}
        </Button>
      </DialogFooter>
    </DialogContent>
  );
}