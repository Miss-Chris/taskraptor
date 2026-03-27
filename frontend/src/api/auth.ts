import { apiRequest } from "./client";

export interface User {
  id: number;
  email: string;
}

export const authApi = {
  login: (email: string, password: string) =>
    apiRequest<User>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),

  logout: () =>
    apiRequest<{ ok: boolean }>("/api/auth/logout", { method: "POST" }),

  me: () => apiRequest<User>("/api/auth/me"),
};
