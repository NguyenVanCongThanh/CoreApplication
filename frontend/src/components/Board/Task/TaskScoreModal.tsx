"use client";

import React, { useState, useEffect } from "react";
import { X, Plus, Trash2, Save, Check } from "lucide-react";
import { Task, User } from "@/types";
import { taskScoreService, TaskScoreResponse } from "@/services/taskScoreService";
import { useAuth } from "@/hooks/useAuth";

interface TaskScoreModalProps {
  task: Task;
  users: User[];
  isOpen: boolean;
  onClose: () => void;
  currentUserId: number;
  onScoresUpdated?: () => void;
}

const TaskScoreModal: React.FC<TaskScoreModalProps> = ({
  task,
  users,
  isOpen,
  onClose,
  currentUserId,
  onScoresUpdated,
}) => {
  const { isAdmin, isManager } = useAuth();
  const [scores, setScores] = useState<TaskScoreResponse[]>([]);
  const [loading, setLoading] = useState(false);
  const [editingScore, setEditingScore] = useState<{
    userId: number;
    score: number;
  } | null>(null);
  const [deductingScore, setDeductingScore] = useState<{
    userId: number;
    amount: number;
    reason: string;
  } | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen && task?.id) {
      loadScores();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, task?.id]);

  const loadScores = async () => {
    try {
      setLoading(true);
      const taskScores = await taskScoreService.getTaskScores(task.id as number);
      setScores(taskScores);
      setError(null);
    } catch (err) {
      setError("Failed to load scores");
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleSetScore = async (userId: number, score: number) => {
    try {
      setLoading(true);
      await taskScoreService.setScore(
        {
          taskId: task.id as number,
          userId,
          score,
          notes: "Set by admin/manager",
        },
        currentUserId
      );
      await loadScores();
      setEditingScore(null);
      setError(null);
    } catch (err) {
      setError("Failed to set score");
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleDeductScore = async () => {
    if (!deductingScore) return;
    try {
      setLoading(true);
      await taskScoreService.deductScore(
        task.id as number,
        deductingScore.userId,
        deductingScore.amount,
        deductingScore.reason,
        currentUserId
      );
      await loadScores();
      setDeductingScore(null);
      setError(null);
    } catch (err) {
      setError("Failed to deduct score");
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleToggleApply = async (userId: number, currentApplied: boolean) => {
    try {
      setLoading(true);
      await taskScoreService.toggleApplyScore(
        task.id as number,
        userId,
        !currentApplied,
        currentUserId
      );
      await loadScores();
      setError(null);
    } catch (err) {
      setError("Failed to update score status");
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleApplyAllScores = async () => {
    try {
      setLoading(true);
      await taskScoreService.applyScoresToTask(task.id as number, currentUserId);
      await loadScores();
      onScoresUpdated?.();
      setError(null);
    } catch (err) {
      setError("Failed to apply scores");
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteScore = async (userId: number) => {
    if (!confirm("Are you sure you want to delete this score?")) return;
    try {
      setLoading(true);
      await taskScoreService.deleteScore(task.id as number, userId, currentUserId);
      await loadScores();
      setError(null);
    } catch (err) {
      setError("Failed to delete score");
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleInitializeScores = async () => {
    const initialScore = prompt("Enter initial score for all assignees (e.g., 10)", "10");
    if (!initialScore) return;

    try {
      setLoading(true);
      await taskScoreService.initializeScoresForTask(
        task.id as number,
        parseInt(initialScore),
        currentUserId
      );
      await loadScores();
      setError(null);
    } catch (err) {
      setError("Failed to initialize scores");
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const canManageScores = isAdmin || isManager;
  const assignedUserIds = task?.assignees || [];
  const taskAssignees = users.filter((u) =>
    assignedUserIds.some((id) => id.toString() === u.id.toString())
  );

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full mx-4 max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="sticky top-0 bg-gradient-to-r from-blue-600 to-purple-600 text-white p-6 flex justify-between items-center">
          <div>
            <h2 className="text-xl font-bold">Manage Scores</h2>
            <p className="text-blue-100 text-sm">{task?.title}</p>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-white hover:bg-opacity-20 rounded-lg"
          >
            <X size={24} />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6">
          {/* Error */}
          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">
              {error}
            </div>
          )}

          {/* Permissions Warning */}
          {!canManageScores && (
            <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 text-yellow-700">
              You do not have permission to manage scores. Only Admin and Manager can manage scores.
            </div>
          )}

          {/* Action Buttons */}
          {canManageScores && (
            <div className="flex gap-3 flex-wrap">
              <button
                onClick={handleInitializeScores}
                disabled={loading}
                className="flex items-center gap-2 px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 disabled:opacity-50"
              >
                <Plus size={18} />
                Initialize Scores
              </button>
              <button
                onClick={handleApplyAllScores}
                disabled={loading}
                className="flex items-center gap-2 px-4 py-2 bg-green-500 text-white rounded hover:bg-green-600 disabled:opacity-50"
              >
                <Check size={18} />
                Apply All Scores
              </button>
            </div>
          )}

          {/* Scores Table */}
          {loading ? (
            <div className="text-center py-8">
              <div className="inline-block animate-spin">⏳</div>
              <p className="text-gray-600 mt-2">Loading scores...</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b-2 border-gray-200">
                    <th className="text-left py-3 px-4 font-semibold text-gray-700">User</th>
                    <th className="text-center py-3 px-4 font-semibold text-gray-700">Score</th>
                    <th className="text-center py-3 px-4 font-semibold text-gray-700">Applied</th>
                    <th className="text-center py-3 px-4 font-semibold text-gray-700">Applied At</th>
                    <th className="text-center py-3 px-4 font-semibold text-gray-700">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {taskAssignees.map((assignee) => {
                    const userScore = scores.find((s) => s.userId === assignee.id);
                    const isEditing =
                      editingScore?.userId === assignee.id;
                    const isDeducting =
                      deductingScore?.userId === assignee.id;

                    return (
                      <tr key={assignee.id} className="border-b border-gray-200 hover:bg-gray-50">
                        <td className="py-3 px-4">
                          <div>
                            <p className="font-medium text-gray-900">
                              {assignee.name}
                            </p>
                            <p className="text-gray-500 text-xs">
                              {assignee.code} - {assignee.team}
                            </p>
                          </div>
                        </td>
                        <td className="py-3 px-4 text-center">
                          {isEditing ? (
                            <div className="flex gap-2 items-center justify-center">
                              <input
                                type="number"
                                value={editingScore.score}
                                onChange={(e) =>
                                  setEditingScore({
                                    ...editingScore,
                                    score: parseInt(e.target.value) || 0,
                                  })
                                }
                                className="w-20 border rounded px-2 py-1"
                              />
                              <button
                                onClick={() =>
                                  handleSetScore(assignee.id as number, editingScore.score)
                                }
                                className="text-green-600 hover:text-green-700"
                              >
                                <Save size={16} />
                              </button>
                            </div>
                          ) : (
                            <span className="text-lg font-bold text-gray-900">
                              {userScore?.score || 0}
                            </span>
                          )}
                        </td>
                        <td className="py-3 px-4 text-center">
                          {userScore?.applied ? (
                            <span className="inline-flex items-center gap-1 bg-green-100 text-green-800 px-3 py-1 rounded-full text-xs font-medium">
                              <Check size={14} /> Applied
                            </span>
                          ) : (
                            <span className="inline-block bg-gray-100 text-gray-600 px-3 py-1 rounded-full text-xs font-medium">
                              Not Applied
                            </span>
                          )}
                        </td>
                        <td className="py-3 px-4 text-center text-xs text-gray-500">
                          {userScore?.appliedAt
                            ? new Date(userScore.appliedAt).toLocaleDateString("vi-VN")
                            : "-"}
                        </td>
                        <td className="py-3 px-4 text-center">
                          {canManageScores && (
                            <div className="flex gap-2 justify-center">
                              {!isEditing && !isDeducting && (
                                <>
                                  <button
                                    onClick={() =>
                                      setEditingScore({
                                        userId: assignee.id as number,
                                        score: userScore?.score || 0,
                                      })
                                    }
                                    className="text-blue-600 hover:text-blue-700 font-medium text-xs"
                                  >
                                    Edit
                                  </button>
                                  <button
                                    onClick={() =>
                                      handleToggleApply(
                                        assignee.id as number,
                                        userScore?.applied || false
                                      )
                                    }
                                    className={`text-xs font-medium ${
                                      userScore?.applied
                                        ? "text-red-600 hover:text-red-700"
                                        : "text-green-600 hover:text-green-700"
                                    }`}
                                  >
                                    {userScore?.applied ? "Unapply" : "Apply"}
                                  </button>
                                  <button
                                    onClick={() =>
                                      setDeductingScore({
                                        userId: assignee.id as number,
                                        amount: 0,
                                        reason: "",
                                      })
                                    }
                                    className="text-orange-600 hover:text-orange-700 font-medium text-xs"
                                  >
                                    Deduct
                                  </button>
                                  <button
                                    onClick={() =>
                                      handleDeleteScore(assignee.id as number)
                                    }
                                    className="text-red-600 hover:text-red-700"
                                  >
                                    <Trash2 size={16} />
                                  </button>
                                </>
                              )}
                            </div>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          {/* Deduct Score Form */}
          {deductingScore && canManageScores && (
            <div className="border border-orange-200 rounded-lg p-4 bg-orange-50">
              <h3 className="font-semibold text-gray-900 mb-3">
                Deduct Score from{" "}
                {taskAssignees.find((u) => u.id === deductingScore.userId)?.name}
              </h3>
              <div className="space-y-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Amount to Deduct
                  </label>
                  <input
                    type="number"
                    value={deductingScore.amount}
                    onChange={(e) =>
                      setDeductingScore({
                        ...deductingScore,
                        amount: parseInt(e.target.value) || 0,
                      })
                    }
                    className="w-full border rounded px-3 py-2"
                    min="0"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Reason
                  </label>
                  <input
                    type="text"
                    value={deductingScore.reason}
                    onChange={(e) =>
                      setDeductingScore({
                        ...deductingScore,
                        reason: e.target.value,
                      })
                    }
                    placeholder="e.g., Late submission, incorrect work"
                    className="w-full border rounded px-3 py-2"
                  />
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={handleDeductScore}
                    disabled={loading || deductingScore.amount <= 0}
                    className="flex-1 px-4 py-2 bg-orange-600 text-white rounded hover:bg-orange-700 disabled:opacity-50"
                  >
                    Deduct Points
                  </button>
                  <button
                    onClick={() => setDeductingScore(null)}
                    className="flex-1 px-4 py-2 bg-gray-200 text-gray-800 rounded hover:bg-gray-300"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="bg-gray-50 border-t p-4 flex justify-end gap-3">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-gray-200 text-gray-800 rounded hover:bg-gray-300"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};

export default TaskScoreModal;
