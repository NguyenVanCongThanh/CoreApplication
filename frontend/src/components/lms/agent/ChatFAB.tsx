"use client";

/**
 * ChatFAB — floating action button to toggle the AI Chat Sidebar.
 *
 * Fixed position, bottom-right. Shows a sparkle icon with a subtle
 * pulse animation. Manages the open/close state of the ChatSidebar.
 */
import { useState } from "react";
import { Sparkles, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { ChatSidebar } from "./ChatSidebar";

export function ChatFAB() {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <>
      {/* The sidebar */}
      <ChatSidebar isOpen={isOpen} onClose={() => setIsOpen(false)} />

      {/* Floating action button */}
      <button
        onClick={() => setIsOpen((prev) => !prev)}
        className={cn(
          "fixed bottom-6 right-6 z-[62]",
          "w-14 h-14 rounded-full",
          "flex items-center justify-center",
          "shadow-lg shadow-blue-500/25 dark:shadow-blue-500/10",
          "transition-all duration-300 ease-in-out",
          "active:scale-90",
          isOpen
            ? "bg-slate-700 dark:bg-slate-600 hover:bg-slate-800 dark:hover:bg-slate-500 rotate-90"
            : "bg-gradient-to-br from-blue-500 to-indigo-600 hover:from-blue-600 hover:to-indigo-700 rotate-0",
        )}
        title={isOpen ? "Đóng AI Chat" : "Mở AI Chat"}
        aria-label={isOpen ? "Đóng AI Chat" : "Mở AI Chat"}
      >
        {isOpen ? (
          <X className="w-5 h-5 text-white" />
        ) : (
          <>
            <Sparkles className="w-5 h-5 text-white" />
            {/* Pulse ring */}
            <span
              className={cn(
                "absolute inset-0 rounded-full",
                "bg-blue-400/30 dark:bg-blue-400/20",
                "animate-ping",
                "pointer-events-none",
              )}
              style={{ animationDuration: "3s" }}
            />
          </>
        )}
      </button>
    </>
  );
}
