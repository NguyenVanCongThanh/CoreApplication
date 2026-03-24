const STATUS_MAP = {
  PENDING: {
    label: "Pending",
    color:
      "bg-yellow-50 dark:bg-yellow-950/20 text-yellow-700 dark:text-yellow-400 border border-yellow-200 dark:border-yellow-800",
  },
  IN_PROGRESS: {
    label: "In Progress",
    color:
      "bg-blue-50 dark:bg-blue-950/20 text-blue-700 dark:text-blue-400 border border-blue-200 dark:border-blue-800",
  },
  COMPLETED: {
    label: "Completed",
    color:
      "bg-green-50 dark:bg-green-950/20 text-green-700 dark:text-green-400 border border-green-200 dark:border-green-800",
  },
  POSTPONED: {
    label: "Postponed",
    color:
      "bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700",
  },
  APPROVED: {
    label: "Approved",
    color:
      "bg-green-50 dark:bg-green-950/20 text-green-700 dark:text-green-400 border border-green-200 dark:border-green-800",
  },
  DENIED: {
    label: "Denied",
    color:
      "bg-red-50 dark:bg-red-950/20 text-red-700 dark:text-red-400 border border-red-200 dark:border-red-800",
  },
  EXPIRED: {
    label: "Expired",
    color:
      "bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700",
  },
};

export default STATUS_MAP;
