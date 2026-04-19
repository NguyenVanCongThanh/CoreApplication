"use client";

import { AdminDashboard } from "@/components/dashboard/admin/AdminDashboard";
import GlobalKnowledgeGraphPanel from "@/components/lms/teacher/ai/GlobalKnowledgeGraphPanel";
import { useState } from "react";
import { BrainCircuit, ChevronDown } from "lucide-react";

export default function AdminPage() {
  const [graphOpen, setGraphOpen] = useState(true);

  return (
    <div className="space-y-8">
      <AdminDashboard />

      <section>
        <button
          onClick={() => setGraphOpen(v => !v)}
          className="w-full flex items-center justify-between px-5 py-4 bg-slate-50 dark:bg-slate-950 border border-slate-800 rounded-2xl hover:border-slate-700 transition-colors group"
        >
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-xl bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center">
              <BrainCircuit className="w-4 h-4 text-indigo-400" />
            </div>
            <div className="text-left">
              <p className="font-bold text-slate-950 dark:text-slate-50 text-sm">Global Knowledge Graph</p>
              <p className="text-xs text-slate-500 mt-0.5">
                Toàn bộ knowledge nodes & liên kết từ tất cả khóa học trong hệ thống
              </p>
            </div>
          </div>
          <ChevronDown
            className={`w-4 h-4 text-slate-500 transition-transform duration-200 ${graphOpen ? "rotate-180" : ""}`}
          />
        </button>

        {graphOpen && (
          <div className="mt-3 rounded-2xl overflow-hidden" style={{ height: 680 }}>
            <GlobalKnowledgeGraphPanel
              title="Global Knowledge Graph — Toàn hệ thống"
              global={true}
            />
          </div>
        )}
      </section>
    </div>
  );
}