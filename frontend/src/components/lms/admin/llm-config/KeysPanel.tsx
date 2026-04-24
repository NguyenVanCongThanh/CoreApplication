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
import type { LlmApiKey, LlmProvider } from "@/services/llmConfigService";
import { llmConfigService } from "@/services/llmConfigService";
import { StatusBadge } from "./StatusBadge";

type Props = {
  keys: LlmApiKey[];
  providers: LlmProvider[];
  onChanged: () => void;
};

export function KeysPanel({ keys, providers, onChanged }: Props) {
  const providerById = new Map(providers.map((p) => [p.id, p]));

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">API Keys</h2>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Mỗi provider có thể có nhiều key. Gateway tự chọn key least-loaded và cooldown key khi gặp 429.
          </p>
        </div>
        <AddKeyDialog providers={providers} onSaved={onChanged} />
      </div>

      <div className="overflow-hidden rounded-lg border border-slate-200 dark:border-slate-800">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 dark:bg-slate-900/60 text-slate-500 text-xs uppercase">
            <tr>
              <th className="px-4 py-2 text-left">Provider</th>
              <th className="px-4 py-2 text-left">Alias</th>
              <th className="px-4 py-2 text-left">Fingerprint</th>
              <th className="px-4 py-2 text-left">Status</th>
              <th className="px-4 py-2 text-right">Requests / ngày</th>
              <th className="px-4 py-2 text-right">Tokens / ngày</th>
              <th className="px-4 py-2 text-right">Quota tokens/ngày</th>
              <th className="px-4 py-2" />
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
            {keys.map((k) => (
              <KeyRow
                key={k.id} k={k}
                provider={providerById.get(k.provider_id)}
                onChanged={onChanged}
              />
            ))}
            {keys.length === 0 && (
              <tr>
                <td colSpan={8} className="px-4 py-8 text-center text-slate-400">
                  Chưa có API key nào.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function KeyRow({
  k, provider, onChanged,
}: {
  k: LlmApiKey;
  provider?: LlmProvider;
  onChanged: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const toggle = async (next: LlmApiKey["status"]) => {
    setBusy(true);
    try {
      await llmConfigService.updateApiKey(k.id, { status: next });
      onChanged();
    } finally {
      setBusy(false);
    }
  };
  const remove = async () => {
    if (!confirm(`Xoá key "${k.alias}"?`)) return;
    setBusy(true);
    try {
      await llmConfigService.deleteApiKey(k.id);
      onChanged();
    } finally {
      setBusy(false);
    }
  };

  return (
    <tr className="hover:bg-slate-50 dark:hover:bg-slate-900/40">
      <td className="px-4 py-3 font-mono text-xs">{provider?.code ?? `#${k.provider_id}`}</td>
      <td className="px-4 py-3">{k.alias}</td>
      <td className="px-4 py-3 font-mono text-xs">{k.fingerprint}</td>
      <td className="px-4 py-3"><StatusBadge status={k.status} /></td>
      <td className="px-4 py-3 text-right tabular-nums">{k.used_today_requests.toLocaleString()}</td>
      <td className="px-4 py-3 text-right tabular-nums">{k.used_today_tokens.toLocaleString()}</td>
      <td className="px-4 py-3 text-right tabular-nums">
        {k.daily_token_limit?.toLocaleString() ?? "—"}
      </td>
      <td className="px-4 py-3 text-right">
        <div className="flex justify-end gap-2">
          {k.status === "active" ? (
            <Button variant="outline" size="sm" onClick={() => toggle("disabled")} disabled={busy}>
              Tắt
            </Button>
          ) : (
            <Button variant="outline" size="sm" onClick={() => toggle("active")} disabled={busy}>
              Kích hoạt
            </Button>
          )}
          <Button variant="destructive" size="sm" onClick={remove} disabled={busy}>
            Xoá
          </Button>
        </div>
      </td>
    </tr>
  );
}

function AddKeyDialog({
  providers, onSaved,
}: {
  providers: LlmProvider[];
  onSaved: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [providerId, setProviderId] = useState<string>(
    providers[0]?.id ? String(providers[0].id) : ""
  );
  const [alias, setAlias] = useState("");
  const [plaintext, setPlaintext] = useState("");
  const [daily, setDaily] = useState<string>("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const save = async () => {
    if (!providerId || !alias || !plaintext) return;
    setSaving(true);
    setError(null);
    try {
      await llmConfigService.createApiKey({
        provider_id: Number(providerId),
        alias,
        plaintext_key: plaintext,
        daily_token_limit: daily ? Number(daily) : null,
      });
      setAlias("");
      setPlaintext("");
      setDaily("");
      setOpen(false);
      onSaved();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button disabled={providers.length === 0}>+ Thêm API key</Button>
      </DialogTrigger>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Thêm API key</DialogTitle>
          <DialogDescription>
            Key sẽ được mã hoá (Fernet) trước khi lưu. Chỉ fingerprint được hiển thị sau khi lưu.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3">
          <div>
            <Label>Provider</Label>
            <Select value={providerId} onValueChange={setProviderId}>
              <SelectTrigger>
                <SelectValue placeholder="Chọn provider" />
              </SelectTrigger>
              <SelectContent>
                {providers.map((p) => (
                  <SelectItem key={p.id} value={String(p.id)}>{p.display_name} ({p.code})</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label>Alias</Label>
            <Input value={alias} onChange={(e) => setAlias(e.target.value)} placeholder="groq-prod-01" />
          </div>
          <div>
            <Label>API key</Label>
            <Input
              type="password"
              value={plaintext}
              onChange={(e) => setPlaintext(e.target.value)}
              placeholder="sk-…"
              autoComplete="new-password"
            />
          </div>
          <div>
            <Label>Daily token limit (tuỳ chọn)</Label>
            <Input
              type="number"
              value={daily}
              onChange={(e) => setDaily(e.target.value)}
              placeholder="vd 1000000"
            />
          </div>
          {error && <p className="text-sm text-rose-600">{error}</p>}
        </div>

        <DialogFooter>
          <Button onClick={save} disabled={saving || !alias || !plaintext || !providerId}>
            {saving ? "Đang lưu…" : "Lưu"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}