import { apiRequest } from "./client";

export interface PendingChannelRequest {
  join_code: string;
  status: "pending" | "fulfilled" | "expired";
  created_at: string;
}

export interface ChannelStatus {
  channel_type: "telegram";
  is_connected: boolean;
  connected_at: string | null;
  telegram_chat_id: number | null;
  telegram_username: string | null;
  pending_request: PendingChannelRequest | null;
}

export const channelsApi = {
  getStatus: () => apiRequest<ChannelStatus>("/api/channels/"),

  createTelegramRequest: (regenerate = false) =>
    apiRequest<ChannelStatus>("/api/channels/requests/telegram", {
      method: "POST",
      body: JSON.stringify({ regenerate }),
    }),
};
