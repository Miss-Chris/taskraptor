import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { channelsApi } from "../api/channels";

export function TelegramChannelCard() {
  const queryClient = useQueryClient();
  const { data: channel, isLoading, isError } = useQuery({
    queryKey: ["channel-status"],
    queryFn: channelsApi.getStatus,
    refetchInterval: (query) => (query.state.data?.is_connected ? false : 3000),
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["channel-status"] });

  const createRequest = useMutation({
    mutationFn: (regenerate: boolean) => channelsApi.createTelegramRequest(regenerate),
    onSuccess: invalidate,
  });

  const unlinkRequest = useMutation({
    mutationFn: channelsApi.unlinkTelegram,
    onSuccess: invalidate,
  });

  const isBusy = isLoading || createRequest.isPending || unlinkRequest.isPending;

  return (
    <section className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-semibold text-gray-900">Telegram</h2>
            {!isLoading && channel && (
              <span
                className={`rounded-full px-2.5 py-1 text-xs font-semibold ${
                  channel.is_connected
                    ? "bg-emerald-100 text-emerald-700"
                    : "bg-amber-100 text-amber-700"
                }`}
              >
                {channel.is_connected ? "Connected" : "Not connected"}
              </span>
            )}
          </div>

          {channel?.is_connected ? (
            <p className="text-sm text-gray-600">
              Linked{channel.telegram_username ? ` as @${channel.telegram_username}` : ""}.
            </p>
          ) : (
            <>
              {channel?.pending_request ? (
                <>
                  <p className="text-sm text-gray-600">
                    Message the bot with{" "}
                    <span className="font-mono font-semibold text-gray-900">
                      JOIN {channel.pending_request.join_code}
                    </span>{" "}
                    to connect.
                  </p>
                  <div className="rounded-xl border border-gray-200 bg-gray-50 px-4 py-3">
                    <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">
                      Join code
                    </p>
                    <p className="mt-1 font-mono text-lg font-semibold text-gray-900">
                      {channel.pending_request.join_code}
                    </p>
                  </div>
                </>
              ) : (
                !isLoading && (
                  <p className="text-sm text-gray-500">
                    Generate a code to link your Telegram account.
                  </p>
                )
              )}
            </>
          )}

          {isError && (
            <p className="text-sm text-red-600">Could not load Telegram status.</p>
          )}
          {createRequest.isError && (
            <p className="text-sm text-red-600">Failed to create join code. Please try again.</p>
          )}
          {unlinkRequest.isError && (
            <p className="text-sm text-red-600">Failed to unlink. Please try again.</p>
          )}
        </div>

        <div className="flex shrink-0 flex-col gap-2">
          {channel?.is_connected ? (
            <button
              type="button"
              onClick={() => unlinkRequest.mutate()}
              disabled={isBusy}
              className="rounded-lg border border-gray-200 px-4 py-2 text-sm font-medium text-gray-600 hover:border-red-300 hover:text-red-600 disabled:opacity-50"
            >
              {unlinkRequest.isPending ? "Unlinking…" : "Unlink"}
            </button>
          ) : (
            <button
              type="button"
              onClick={() => createRequest.mutate(Boolean(channel?.pending_request))}
              disabled={isBusy}
              className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
            >
              {createRequest.isPending
                ? "Saving…"
                : channel?.pending_request
                  ? "Regenerate code"
                  : "Generate code"}
            </button>
          )}
        </div>
      </div>
    </section>
  );
}
