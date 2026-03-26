"use client";
import React from "react";
import { User } from "@/types";
import Avatar from "./Avatar";
import { X } from "lucide-react";

export default function DetailModal({ user, onClose }: { user: User | null; onClose: () => void; }) {
  if (!user) return null;
  
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />

      {/* Modal */}
      <div className="relative z-10 w-full max-w-lg bg-white dark:bg-slate-900 rounded-2xl shadow-lg overflow-hidden">
        {/* Header */}
        <div className="p-4 sm:p-6 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Avatar code={user.code} size={56} />
            <div className="min-w-0">
              <h3 className="text-lg font-bold text-slate-900 dark:text-slate-50 truncate">
                {user.name}
              </h3>
              <p className="text-sm text-slate-500 dark:text-slate-400 truncate">
                {user.email}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="flex-shrink-0 p-2 text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200 transition-colors duration-200"
            aria-label="Close dialog"
          >
            <X size={20} />
          </button>
        </div>

        {/* Content */}
        <div className="p-4 sm:p-6 space-y-5">
          {/* Info Grid */}
          <div className="grid grid-cols-2 gap-4">
            {/* Code */}
            <div>
              <label className="block text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-1">
                Code
              </label>
              <p className="text-sm font-medium text-slate-900 dark:text-slate-50">
                {user.code}
              </p>
            </div>

            {/* Role */}
            <div>
              <label className="block text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-1">
                Role
              </label>
              <p className="text-sm font-medium text-slate-900 dark:text-slate-50">
                {user.role}
              </p>
            </div>

            {/* Team */}
            <div>
              <label className="block text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-1">
                Team
              </label>
              <p className="text-sm font-medium text-slate-900 dark:text-slate-50">
                {user.team}
              </p>
            </div>

            {/* Type */}
            <div>
              <label className="block text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-1">
                Type
              </label>
              <p className="text-sm font-medium text-slate-900 dark:text-slate-50">
                {user.type}
              </p>
            </div>

            {/* Score */}
            <div>
              <label className="block text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-1">
                Score
              </label>
              <p className="text-sm font-bold text-blue-600 dark:text-blue-400">
                {user.score}
              </p>
            </div>

            {/* Date Added */}
            <div>
              <label className="block text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-1">
                Date Added
              </label>
              <p className="text-sm font-medium text-slate-900 dark:text-slate-50">
                {user.dateAdded
                  ? new Date(user.dateAdded).toLocaleDateString()
                  : "Chưa xác định"}
              </p>
            </div>
          </div>

          {/* Status */}
          <div className="pt-4 border-t border-slate-200 dark:border-slate-800">
            <label className="block text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-2">
              Status
            </label>
            <div className="flex items-center gap-2">
              <span
                className={`inline-block h-2 w-2 rounded-full ${
                  user.status ? "bg-green-600" : "bg-slate-400"
                }`}
              />
              <span className="text-sm font-medium text-slate-900 dark:text-slate-50">
                {user.status ? "Active" : "Inactive"}
              </span>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="flex justify-end gap-3 p-4 sm:p-6 border-t border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/50">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-semibold transition-colors duration-200 active:scale-95"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
