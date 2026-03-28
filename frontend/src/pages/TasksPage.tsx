import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { authApi } from "../api/auth";
import { TelegramChannelCard } from "../components/TelegramChannelCard";
import { tasksApi } from "../api/tasks";
import { CreateTaskForm } from "../components/CreateTaskForm";
import { TaskItem } from "../components/TaskItem";

export function TasksPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const { data: user } = useQuery({
    queryKey: ["me"],
    queryFn: authApi.me,
  });

  const { data: tasks = [], isLoading } = useQuery({
    queryKey: ["tasks"],
    queryFn: tasksApi.list,
  });

  const logout = useMutation({
    mutationFn: authApi.logout,
    onSuccess: () => {
      queryClient.clear();
      navigate("/login");
    },
  });

  const pending = tasks.filter((t) => t.status === "pending");
  const done = tasks.filter((t) => t.status === "done");

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="border-b border-gray-200 bg-white px-6 py-4">
        <div className="mx-auto flex max-w-2xl items-center justify-between">
          <h1 className="text-xl font-bold text-gray-900">TaskRaptor</h1>
          <div className="flex items-center gap-4">
            <span className="text-sm text-gray-500">{user?.email}</span>
            <button
              onClick={() => logout.mutate()}
              className="text-sm text-gray-500 hover:text-gray-800"
            >
              Sign out
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-2xl px-6 py-8 space-y-6">
        <TelegramChannelCard />
        <CreateTaskForm />

        {isLoading ? (
          <p className="text-center text-gray-400">Loading tasks…</p>
        ) : tasks.length === 0 ? (
          <p className="text-center text-gray-400">
            No tasks yet. Add one above.
          </p>
        ) : (
          <>
            {pending.length > 0 && (
              <section className="space-y-2">
                <h2 className="text-xs font-semibold uppercase tracking-wider text-gray-400">
                  Pending
                </h2>
                {pending.map((task) => (
                  <TaskItem key={task.id} task={task} />
                ))}
              </section>
            )}

            {done.length > 0 && (
              <section className="space-y-2">
                <h2 className="text-xs font-semibold uppercase tracking-wider text-gray-400">
                  Done
                </h2>
                {done.map((task) => (
                  <TaskItem key={task.id} task={task} />
                ))}
              </section>
            )}
          </>
        )}
      </main>
    </div>
  );
}
