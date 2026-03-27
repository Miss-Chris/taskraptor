import { apiRequest } from "./client";

export interface Task {
  id: number;
  description: string;
  status: "pending" | "done";
  created_at: string;
  due_at: string | null;
}

export const tasksApi = {
  list: () => apiRequest<Task[]>("/api/tasks/"),

  create: (description: string, due_at?: string) =>
    apiRequest<Task>("/api/tasks/", {
      method: "POST",
      body: JSON.stringify({ description, due_at: due_at ?? null }),
    }),

  update: (id: number, data: Partial<Pick<Task, "description" | "status" | "due_at">>) =>
    apiRequest<Task>(`/api/tasks/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),

  delete: (id: number) =>
    apiRequest<{ ok: boolean }>(`/api/tasks/${id}`, { method: "DELETE" }),
};
