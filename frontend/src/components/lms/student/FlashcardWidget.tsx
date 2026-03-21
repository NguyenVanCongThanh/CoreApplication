"use client";

import { useEffect, useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Sparkles,
  Layers,
  CheckCircle2,
  X,
  Clock,
  ChevronRight,
  RotateCcw,
  AlertCircle,
  Calendar,
  Rotate3d,
} from "lucide-react";
import analyticsService, { FlashcardStatsResponse } from "@/services/analyticsService";
import flashcardService, { FlashcardDueItem } from "@/services/flashcardService";
import { cn } from "@/lib/utils";

interface Props {
  courseId: number;
}

const QUALITY_BTNS = [
  { q: 0 as const, label: "Quên hoàn toàn", short: "0", cls: "bg-red-500 hover:bg-red-600 text-white" },
  { q: 1 as const, label: "Gần như quên", short: "1", cls: "bg-orange-500 hover:bg-orange-600 text-white" },
  { q: 2 as const, label: "Nhớ khi xem đáp án", short: "2", cls: "bg-amber-500 hover:bg-amber-600 text-white" },
  { q: 3 as const, label: "Nhớ nhưng khó", short: "3", cls: "bg-yellow-400 hover:bg-yellow-500 text-white" },
  { q: 4 as const, label: "Nhớ tốt", short: "4", cls: "bg-green-500 hover:bg-green-600 text-white" },
  { q: 5 as const, label: "Nhớ hoàn hảo", short: "5", cls: "bg-emerald-500 hover:bg-emerald-600 text-white" },
];

export function FlashcardWidget({ courseId }: Props) {
  const [stats, setStats] = useState<FlashcardStatsResponse | null>(null);
  const [dueCards, setDueCards] = useState<FlashcardDueItem[]>([]);
  const [current, setCurrent] = useState(0);
  const [isFlipped, setIsFlipped] = useState(false);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");
  const [session, setSession] = useState<"idle" | "reviewing">("idle");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [sRes, cardsRes] = await Promise.all([
        analyticsService.getFlashcardStats(courseId),
        flashcardService.listDueFlashcards(courseId),
      ]);
      setStats(sRes.data);
      setDueCards(cardsRes.data || []);
    } catch (e: any) {
      setError(e?.response?.data?.message || "Không tải được dữ liệu Flashcard.");
    } finally {
      setLoading(false);
    }
  }, [courseId]);

  useEffect(() => {
    load();
  }, [load]);

  const handleRecord = async (quality: number) => {
    const item = dueCards[current];
    if (!item) return;
    setSubmitting(true);
    try {
      await flashcardService.reviewFlashcard(item.flashcard.id, quality);
      if (current + 1 >= dueCards.length) {
        setDone(true);
        await load();
      } else {
        setCurrent((c) => c + 1);
        setIsFlipped(false);
      }
    } catch {
      // fail silently & advance
      if (current + 1 >= dueCards.length) setDone(true);
      else {
        setCurrent((c) => c + 1);
        setIsFlipped(false);
      }
    } finally {
      setSubmitting(false);
    }
  };

  const startSession = () => {
    setCurrent(0);
    setIsFlipped(false);
    setDone(false);
    setSession("reviewing");
  };

  if (loading) {
    return (
      <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-5">
        <div className="flex items-center gap-3">
          <div className="w-5 h-5 border-2 border-violet-500 border-t-transparent rounded-full animate-spin" />
          <p className="text-sm text-slate-500">Đang tải lịch ôn tập Flashcard…</p>
        </div>
      </div>
    );
  }

  if (error && !stats) {
    return (
      <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-5">
        <div className="flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-amber-500 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-semibold text-slate-700 dark:text-slate-300">
              Lỗi hệ thống
            </p>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">{error}</p>
          </div>
        </div>
      </div>
    );
  }

  // ── Idle state ───────────────────────────────────────────────────────────

  if (session === "idle") {
    const dueToday = stats?.today_due ?? 0;

    return (
      <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
        {/* Header */}
        <div className="flex items-center gap-3 px-5 py-4 border-b border-slate-100 dark:border-slate-800">
          <div className="w-9 h-9 rounded-xl bg-violet-100 dark:bg-violet-950/30 flex items-center justify-center border border-violet-200 dark:border-violet-800">
            <Layers className="w-5 h-5 text-violet-600 dark:text-violet-400" />
          </div>
          <div>
            <p className="font-bold text-slate-900 dark:text-slate-50">Ôn tập Flashcard</p>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Spaced Repetition (Lật thẻ)
            </p>
          </div>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-3 divide-x divide-slate-100 dark:divide-slate-800">
          {[
            {
              icon: <Clock className="w-4 h-4 text-red-500" />,
              label: "Hôm nay",
              value: stats?.today_due ?? 0,
              accent: (stats?.today_due ?? 0) > 0 ? "text-red-600 dark:text-red-400" : "",
            },
            {
              icon: <Calendar className="w-4 h-4 text-blue-500" />,
              label: "Sắp tới",
              value: stats?.upcoming ?? 0,
              accent: "",
            },
            {
              icon: <CheckCircle2 className="w-4 h-4 text-emerald-500" />,
              label: "Đang theo dõi",
              value: stats?.learning_count ?? 0,
              accent: "",
            },
          ].map((s) => (
            <div key={s.label} className="flex flex-col items-center py-4 gap-1">
              {s.icon}
              <p
                className={cn(
                  "text-xl font-extrabold text-slate-900 dark:text-slate-50",
                  s.accent
                )}
              >
                {s.value}
              </p>
              <p className="text-xs text-slate-500 dark:text-slate-400">{s.label}</p>
            </div>
          ))}
        </div>

        {/* Action */}
        <div className="px-5 pb-5">
          {dueToday > 0 ? (
            <button
              onClick={startSession}
              className="w-full flex items-center justify-center gap-2 py-3 bg-violet-600 hover:bg-violet-700 text-white font-semibold rounded-xl transition-all active:scale-95 shadow-sm"
            >
              <Sparkles className="w-4 h-4" />
              Ôn thẻ ngay ({dueToday} thẻ)
              <ChevronRight className="w-4 h-4" />
            </button>
          ) : (
            <div className="flex items-center gap-2 py-3 px-4 bg-emerald-50 dark:bg-emerald-950/20 rounded-xl border border-emerald-200 dark:border-emerald-800">
              <CheckCircle2 className="w-4 h-4 text-emerald-500" />
              <p className="text-sm font-medium text-emerald-700 dark:text-emerald-400">
                Làm tốt lắm! Bạn đã học hết flashcard của hôm nay.
              </p>
            </div>
          )}
        </div>
      </div>
    );
  }

  // ── Done state ────────────────────────────────────────────────────────────

  if (done) {
    return (
      <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm p-8 text-center">
        <CheckCircle2 className="w-12 h-12 text-emerald-500 mx-auto mb-3" />
        <p className="text-xl font-bold text-slate-900 dark:text-slate-50 mb-1">
          Hoàn thành rồi! 🎉
        </p>
        <p className="text-sm text-slate-500 dark:text-slate-400 mb-6">
          Bạn đã ôn tập {dueCards.length} thẻ flashcard hôm nay.
        </p>
        <button
          onClick={() => setSession("idle")}
          className="flex items-center gap-2 mx-auto px-5 py-2.5 bg-violet-600 hover:bg-violet-700 text-white font-semibold rounded-xl transition-all active:scale-95"
        >
          <RotateCcw className="w-4 h-4" />
          Quay lại tổng quan
        </button>
      </div>
    );
  }

  // ── Card session ──────────────────────────────────────────────────────────

  const item = dueCards[current];
  const progress = (current / dueCards.length) * 100;

  return (
    <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden flex flex-col h-[500px]">
      {/* Progress bar */}
      <div className="h-1 w-full bg-slate-100 dark:bg-slate-800 flex-shrink-0">
        <div
          className="h-full bg-violet-500 transition-all duration-500"
          style={{ width: `${progress}%` }}
        />
      </div>

      {/* Header */}
      <div className="flex flex-shrink-0 items-center justify-between px-5 py-3 border-b border-slate-100 dark:border-slate-800">
        <div className="flex items-center gap-2">
          <Layers className="w-4 h-4 text-violet-500" />
          <p className="text-sm font-semibold text-slate-700 dark:text-slate-300">
            Thẻ {current + 1} / {dueCards.length}
          </p>
        </div>
        {item?.node_name && (
          <span className="text-xs text-slate-500 dark:text-slate-400 bg-slate-100 dark:bg-slate-800 px-2 py-0.5 rounded-full truncate max-w-[150px]">
            {item.node_name}
          </span>
        )}
        <button
          onClick={() => setSession("idle")}
          className="p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-400 transition-colors"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Flashcard Area */}
      <div className="flex-1 px-5 py-6 flex flex-col items-center justify-center relative perspective-1000">
        <AnimatePresence mode="wait">
          <motion.div
            key={item?.flashcard.id + (isFlipped ? "-back" : "-front")}
            initial={{ rotateY: isFlipped ? -90 : 90, opacity: 0 }}
            animate={{ rotateY: 0, opacity: 1 }}
            exit={{ rotateY: isFlipped ? 90 : -90, opacity: 0 }}
            transition={{ duration: 0.3 }}
            className={cn(
              "w-full h-full max-w-md mx-auto rounded-3xl p-8 flex flex-col items-center justify-center text-center shadow-md border cursor-pointer",
              isFlipped
                ? "bg-violet-50 dark:bg-violet-900/20 border-violet-200 dark:border-violet-800"
                : "bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700"
            )}
            onClick={() => !isFlipped && setIsFlipped(true)}
            style={{ backfaceVisibility: "hidden" }}
          >
            {isFlipped ? (
              <>
                <p className="text-xs font-semibold text-violet-500 uppercase tracking-widest mb-4">
                  Đáp án
                </p>
                <div className="text-lg md:text-xl font-medium text-slate-800 dark:text-slate-100 leading-relaxed max-h-[220px] overflow-y-auto">
                  {item?.flashcard.back_text}
                </div>
              </>
            ) : (
              <>
                <p className="text-xs font-semibold text-slate-400 uppercase tracking-widest mb-4">
                  Câu hỏi / Khái niệm
                </p>
                <div className="text-xl md:text-2xl font-bold text-slate-900 dark:text-slate-50 leading-snug">
                  {item?.flashcard.front_text}
                </div>
                <div className="mt-8 flex items-center gap-2 text-sm text-slate-400">
                  <Rotate3d className="w-4 h-4" />
                  Nhấn vào thẻ để lật
                </div>
              </>
            )}
          </motion.div>
        </AnimatePresence>
      </div>

      {/* Footer Controls */}
      <div className="flex-shrink-0 px-5 pb-6">
        {!isFlipped ? (
          <div className="h-16 flex items-center justify-center text-slate-400 text-sm">
            <span className="animate-pulse">Hãy tự suy nghĩ câu trả lời trước khi lật thẻ...</span>
          </div>
        ) : (
          <div className="space-y-3 animate-in fade-in slide-in-from-bottom-2 duration-300">
            <p className="text-xs font-semibold text-center text-slate-500 dark:text-slate-400 uppercase tracking-wide">
              Đánh giá trí nhớ của bạn
            </p>
            <div className="grid grid-cols-3 md:grid-cols-6 gap-2">
              {QUALITY_BTNS.map((b) => (
                <button
                  key={b.q}
                  onClick={() => handleRecord(b.q)}
                  disabled={submitting}
                  title={b.label}
                  className={cn(
                    "flex flex-col items-center py-2 px-1 rounded-xl text-xs font-bold transition-all active:scale-95 disabled:opacity-50",
                    b.cls
                  )}
                >
                  <span className="text-lg mb-0.5">{b.short}</span>
                  <span className="font-medium leading-tight text-center opacity-90 hidden md:block">
                    {b.label.split(" ").slice(0, 2).join(" ")}
                  </span>
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
