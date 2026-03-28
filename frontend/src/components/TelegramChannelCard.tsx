import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { channelsApi } from "../api/channels";

export function TelegramChannelCard() {
  const queryClient = useQueryClient();
  const { data: channel, isLoading } = useQuery({
    queryKey: ["channel-status"],
    queryFn: channelsApi.getStatus,
  });

  const createRequest = useMutation({
    mutationFn: (regenerate: boolean) => channelsApi.createTelegramRequest(regenerate),
    onSuccess: (nextStatus) => {
      queryClient.setQueryData(["channel-status"], nextStatus);
    },
  });

  const buttonLabel = channel?.pending_request ? "Regenerate code" : "Create Telegram code";

  return (
    <section className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-semibold text-gray-900">Telegram</h2>
            <span
              className={`rounded-full px-2.5 py-1 text-xs font-semibold ${
                channel?.is_connected
                  ? "bg-emerald-100 text-emerald-700"
                  : "bg-amber-100 text-amber-700"
              }`}
            >
              {channel?.is_connected ? "Connected" : "Not connected"}
            </span>
          </div>
          <p className="text-sm text-gray-600">
            Create a join code, then message the bot with{" "}
            <span className="font-mono font-semibold text-gray-900">
              JOIN {channel?.pending_request?.join_code ?? "&lt;code&gt;"}
            </span>
            .
          </p>
          {channel?.is_connected && (
            <p className="text-sm text-emerald-700">
              Telegram is linked{channel.telegram_username ? ` as @${channel.telegram_username}` : ""}.
            </p>
          )}
          {channel?.pending_request && (
            <div className="rounded-xl border border-gray-200 bg-gray-50 px-4 py-3">
              <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">
                Current join code
              </p>
              <p className="mt-1 font-mono text-lg font-semibold text-gray-900">
                {channel.pending_request.join_code}
              </p>
            </div>
          )}
          {!isLoading && !channel?.pending_request && (
            <p className="text-sm text-gray-500">
              No pending code yet. Create one to start the Telegram link flow.
            </p>
          )}
        </div>

        <button
          type="button"
          onClick={() => createRequest.mutate(Boolean(channel?.pending_request))}
          disabled={createRequest.isPending || isLoading}
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
        >
          {createRequest.isPending ? "Saving…" : buttonLabel}
        </button>
      </div>
    </section>
  );
}
