function ReadonlyField({
  icon: Icon,
  value,
}: {
  icon: React.ElementType;
  value: string;
}) {
  return (
    <div
      className="flex items-center gap-2 rounded-xl p-3 text-sm
                    bg-slate-50 dark:bg-slate-800
                    border border-slate-200 dark:border-slate-700
                    text-slate-600 dark:text-slate-300"
    >
      <Icon className="h-4 w-4 text-blue-600 dark:text-blue-400 flex-shrink-0" />
      <span>{value}</span>
    </div>
  );
}

export default ReadonlyField;
