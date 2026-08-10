import { useState } from "react";
import { apiClient } from "../api/ApiClient";
import { ApiError } from "../api/errors";
import type { VoteResponse } from "../api/types";
import { useI18n } from "../i18n/I18n";
import { useAuth } from "../state/auth";

const SCALE = [1, 2, 3, 4, 5];

export function VoteControl({ workId }: { workId: string }) {
  const { t } = useI18n();
  const isAuthenticated = useAuth((s) => s.isAuthenticated());
  const [vote, setVote] = useState<number>(5);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<VoteResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (!isAuthenticated) {
    return <p className="text-sm text-osap-muted">{t("vote.needLogin")}</p>;
  }

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      const res = await apiClient.post<VoteResponse>(`/works/${encodeURIComponent(workId)}/vote`, { vote });
      setDone(res);
    } catch (e) {
      const code = e instanceof ApiError ? e.code : "UNKNOWN";
      setError(
        code === "UNAUTHORIZED" || code === "FORBIDDEN"
          ? t("vote.needVerified")
          : code === "NOT_FOUND"
            ? t("vote.workNotFound")
            : code === "DUPLICATE_VOTE"
              ? t("vote.alreadyVoted")
              : code === "INVALID_VOTE"
                ? t("vote.scale")
                : t("vote.error"),
      );
    } finally {
      setBusy(false);
    }
  };

  if (done !== null) {
    return (
      <p className="text-sm text-osap-muted">
        {t("vote.voted")}: {done.vote}/5
      </p>
    );
  }

  return (
    <div className="flex items-center gap-2">
      <span className="text-sm text-osap-muted">{t("vote.rate")}:</span>
      {SCALE.map((v) => (
        <button
          key={v}
          type="button"
          onClick={() => setVote(v)}
          className={`rounded border px-2 py-0.5 text-sm ${vote === v ? "border-osap-accent bg-osap-accent text-white" : "border-osap-border text-osap-ink"}`}
        >
          {v}
        </button>
      ))}
      <button
        onClick={submit}
        disabled={busy}
        className="rounded bg-osap-accent px-3 py-1 text-sm text-white disabled:opacity-60"
      >
        {busy ? t("vote.working") : t("vote.submit")}
      </button>
      {error !== null && <span className="text-xs text-red-500">{error}</span>}
    </div>
  );
}
