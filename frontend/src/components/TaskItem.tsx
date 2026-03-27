import { useMutation, useQueryClient } from "@tanstack/react-query";
import { tasksApi, type Task } from "../api/tasks";

interface Props {
  task: Task;
}

export function TaskItem({ task }: Props) {
  const queryClient = useQueryClient();

  const toggle = useMutation({
    mutationFn: () =>
      tasksApi.update(task.id, {
        status: task.status === "pending" ? "done" : "pending",
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["tasks"] }),
  });

  const remove = useMutation({
    mutationFn: () => tasksApi.delete(task.id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["tasks"] }),
  });

  const isDone = task.status === "done";

  return (
    <div className="flex items-start gap-3 rounded-xl border border-gray-200 bg-white px-4 py-3 shadow-sm">
      <button
        onClick={() => toggle.mutate()}
        disabled={toggle.isPending}
        className={`mt-0.5 flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full border-2 transition-colors ${
          isDone
            ? "border-indigo-600 bg-indigo-600"
            : "border-gray-300 hover:border-indigo-400"
        }`}
        aria-label={isDone ? "Mark as pending" : "Mark as done"}
      >
        {isDone && (
          <svg className="h-3 w-3 text-white" viewBox="0 0 12 12" fill="currentColor">
            <path d="M10 3L5 8.5 2 5.5" stroke="currentColor" strokeWidth="1.5" fill="none" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        )}
      </button>

      <div className="min-w-0 flex-1">
        <p className={`text-sm ${isDone ? "text-gray-400 line-through" : "text-gray-900"}`}>
          {task.description}
        </p>
        {task.due_at && (
          <p className="mt-0.5 text-xs text-gray-400">
            Due {new Date(task.due_at).toLocaleDateString()}
          </p>
        )}
      </div>

      <button
        onClick={() => remove.mutate()}
        disabled={remove.isPending}
        className="flex-shrink-0 text-gray-300 hover:text-red-400 disabled:opacity-50"
        aria-label="Delete task"
      >
        <svg className="h-4 w-4" viewBox="0 0 16 16" fill="currentColor">
          <path d="M5.5 5.5a.5.5 0 0 1 .5.5v6a.5.5 0 0 1-1 0V6a.5.5 0 0 1 .5-.5zm2.5 0a.5.5 0 0 1 .5.5v6a.5.5 0 0 1-1 0V6a.5.5 0 0 1 .5-.5zm2.5 0a.5.5 0 0 1 .5.5v6a.5.5 0 0 1-1 0V6a.5.5 0 0 1 .5-.5z"/>
          <path fillRule="evenodd" d="M14.5 3a1 1 0 0 1-1 1H13v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V4h-.5a1 1 0 0 1-1-1V2a1 1 0 0 1 1-1H6a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1h3.5a1 1 0 0 1 1 1v1zM4.118 4 4 4.059V13a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1V4.059L11.882 4H4.118zM2.5 3V2h11v1h-11z"/>
        </svg>
      </button>
    </div>
  );
}
