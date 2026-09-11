import { useCallback, useEffect, useState } from "react";
import { ApiError } from "../api/errors";
import { useI18n } from "../i18n/I18n";
import { useAuth } from "../state/auth";
import {
  supportApiClient,
  type AdminDonationItem,
  type AdminMembershipItem,
} from "../support/supportApiClient";

type Tab = "memberships" | "donations";

const LIMIT = 25;
const MEMBERSHIP_STATUSES = ["active", "past_due", "cancelled", "expired", "pending"];
const MEMBERSHIP_LEVELS = ["supporter", "contributor", "voice", "founder"];
const PERIODICITIES = ["monthly", "yearly"];

function formatMoney(amountMinor: number, currency: string): string {
  try {
    return new Intl.NumberFormat(undefined, {
      style: "currency",
      currency,
    }).format(amountMinor / 100);
  } catch {
    return `${amountMinor} ${currency}`;
  }
}

function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const date = new Date(iso);
  return Number.isNaN(date.getTime())
    ? iso
    : date.toLocaleString(undefined, { dateStyle: "short", timeStyle: "short" });
}

function shortUser(userId: string): string {
  return userId.length > 12 ? `${userId.slice(0, 12)}…` : userId;
}

function isForbidden(e: unknown): boolean {
  return e instanceof ApiError && e.details.status === 403;
}

function statusColor(status: string): string {
  switch (status) {
    case "active":
      return "bg-green-100 text-green-800";
    case "past_due":
      return "bg-amber-100 text-amber-800";
    case "cancelled":
      return "bg-red-100 text-red-800";
    default:
      return "bg-osap-border text-osap-muted";
  }
}

function UserCell({ userId }: { userId: string }) {
  return (
    <span title={userId} className="font-mono text-xs text-osap-muted">
      {shortUser(userId)}
    </span>
  );
}

function Pagination({
  total,
  offset,
  onPrev,
  onNext,
  disabled,
}: {
  total: number;
  offset: number;
  onPrev: () => void;
  onNext: () => void;
  disabled: boolean;
}) {
  const { t } = useI18n();
  const last = offset + LIMIT;
  return (
    <div className="flex items-center justify-between">
      <span className="text-xs text-osap-muted">
        {t("adminPayments.total")}: {total}
      </span>
      <div className="flex items-center gap-2">
        <button
          type="button"
          disabled={offset === 0 || disabled}
          onClick={onPrev}
          className="rounded border border-osap-border px-3 py-1 text-sm disabled:opacity-40"
        >
          {t("pagination.previous")}
        </button>
        <button
          type="button"
          disabled={last >= total || disabled}
          onClick={onNext}
          className="rounded border border-osap-border px-3 py-1 text-sm disabled:opacity-40"
        >
          {t("pagination.next")}
        </button>
      </div>
    </div>
  );
}

function MembershipsTab({ token }: { token: string }) {
  const { t } = useI18n();
  const [items, setItems] = useState<AdminMembershipItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [userDraft, setUserDraft] = useState("");
  const [userQuery, setUserQuery] = useState("");
  const [status, setStatus] = useState("");
  const [level, setLevel] = useState("");
  const [periodicity, setPeriodicity] = useState("");
  const [offset, setOffset] = useState(0);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const page = await supportApiClient.listAdminMemberships(token, {
        user_id: userQuery || undefined,
        status: status || undefined,
        level: level || undefined,
        periodicity: periodicity || undefined,
        limit: LIMIT,
        offset,
      });
      setItems(page.items);
      setTotal(page.total);
    } catch (e) {
      setError(isForbidden(e) ? t("adminPayments.forbidden") : t("adminPayments.loadError"));
    } finally {
      setLoading(false);
    }
  }, [token, userQuery, status, level, periodicity, offset, t]);

  useEffect(() => {
    void load();
  }, [load]);

  const resetOffset = () => setOffset(0);

  const selectCls =
    "rounded border border-osap-border bg-osap-surface px-2 py-1 text-sm";

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <input
          value={userDraft}
          onChange={(e) => setUserDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              setUserQuery(userDraft.trim());
              resetOffset();
            }
          }}
          placeholder={t("adminPayments.userPlaceholder")}
          className="w-52 rounded border border-osap-border bg-osap-surface px-2 py-1 text-sm"
        />
        <select
          value={status}
          onChange={(e) => {
            setStatus(e.target.value);
            resetOffset();
          }}
          className={selectCls}
        >
          <option value="">{t("adminPayments.status")}: {t("adminPayments.all")}</option>
          {MEMBERSHIP_STATUSES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <select
          value={level}
          onChange={(e) => {
            setLevel(e.target.value);
            resetOffset();
          }}
          className={selectCls}
        >
          <option value="">{t("adminPayments.level")}: {t("adminPayments.all")}</option>
          {MEMBERSHIP_LEVELS.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <select
          value={periodicity}
          onChange={(e) => {
            setPeriodicity(e.target.value);
            resetOffset();
          }}
          className={selectCls}
        >
          <option value="">{t("adminPayments.periodicity")}: {t("adminPayments.all")}</option>
          {PERIODICITIES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <button
          type="button"
          onClick={() => {
            setUserQuery(userDraft.trim());
            resetOffset();
          }}
          className="rounded bg-osap-accent px-4 py-1 text-sm text-white"
        >
          {t("adminPayments.filter")}
        </button>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      <div className="overflow-x-auto rounded-lg border border-osap-border">
        <table className="w-full text-left text-sm">
          <thead className="bg-osap-surface text-xs uppercase text-osap-muted">
            <tr>
              <th className="px-3 py-2">{t("adminPayments.user")}</th>
              <th className="px-3 py-2">{t("adminPayments.email")}</th>
              <th className="px-3 py-2">{t("adminPayments.level")}</th>
              <th className="px-3 py-2">{t("adminPayments.periodicity")}</th>
              <th className="px-3 py-2">{t("adminPayments.status")}</th>
              <th className="px-3 py-2 text-right">{t("adminPayments.amount")}</th>
              <th className="px-3 py-2">{t("adminPayments.startedAt")}</th>
              <th className="px-3 py-2">{t("adminPayments.nextRenewal")}</th>
              <th className="px-3 py-2">{t("adminPayments.subscription")}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-osap-border">
            {loading ? (
              <tr>
                <td colSpan={9} className="px-3 py-8 text-center text-osap-muted">
                  …
                </td>
              </tr>
            ) : items.length === 0 ? (
              <tr>
                <td colSpan={9} className="px-3 py-8 text-center text-osap-muted">
                  {t("adminPayments.emptyMemberships")}
                </td>
              </tr>
            ) : (
              items.map((m) => (
                <tr key={m.id} className="odd:bg-osap-bg">
                  <td className="px-3 py-2">
                    <UserCell userId={m.user_id} />
                  </td>
                  <td className="px-3 py-2 text-xs">{m.email_contact || "—"}</td>
                  <td className="px-3 py-2">{m.level}</td>
                  <td className="px-3 py-2">{m.periodicity}</td>
                  <td className="px-3 py-2">
                    <span className={`rounded-full px-2 py-0.5 text-xs ${statusColor(m.status)}`}>
                      {m.status}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-right">
                    {formatMoney(m.amount_minor, m.currency)}
                  </td>
                  <td className="px-3 py-2 text-xs">{formatDate(m.started_at)}</td>
                  <td className="px-3 py-2 text-xs">{formatDate(m.next_renewal_at)}</td>
                  <td className="px-3 py-2 font-mono text-xs text-osap-muted" title={m.subscription_id}>
                    {shortUser(m.subscription_id)}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <Pagination
        total={total}
        offset={offset}
        onPrev={() => setOffset((o) => Math.max(0, o - LIMIT))}
        onNext={() => setOffset((o) => o + LIMIT)}
        disabled={loading}
      />
    </div>
  );
}

function DonationsTab({ token }: { token: string }) {
  const { t } = useI18n();
  const [items, setItems] = useState<AdminDonationItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [userDraft, setUserDraft] = useState("");
  const [userQuery, setUserQuery] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [offset, setOffset] = useState(0);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    const from = dateFrom ? new Date(`${dateFrom}T00:00:00`).toISOString() : undefined;
    const to = dateTo ? new Date(`${dateTo}T23:59:59`).toISOString() : undefined;
    try {
      const page = await supportApiClient.listAdminDonations(token, {
        user_id: userQuery || undefined,
        date_from: from,
        date_to: to,
        limit: LIMIT,
        offset,
      });
      setItems(page.items);
      setTotal(page.total);
    } catch (e) {
      setError(isForbidden(e) ? t("adminPayments.forbidden") : t("adminPayments.loadError"));
    } finally {
      setLoading(false);
    }
  }, [token, userQuery, dateFrom, dateTo, offset, t]);

  useEffect(() => {
    void load();
  }, [load]);

  const resetOffset = () => setOffset(0);

  const inputCls = "rounded border border-osap-border bg-osap-surface px-2 py-1 text-sm";

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <input
          value={userDraft}
          onChange={(e) => setUserDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              setUserQuery(userDraft.trim());
              resetOffset();
            }
          }}
          placeholder={t("adminPayments.userPlaceholder")}
          className={`w-52 ${inputCls}`}
        />
        <label className="flex items-center gap-1 text-xs text-osap-muted">
          {t("adminPayments.dateFrom")}
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => {
              setDateFrom(e.target.value);
              resetOffset();
            }}
            className={inputCls}
          />
        </label>
        <label className="flex items-center gap-1 text-xs text-osap-muted">
          {t("adminPayments.dateTo")}
          <input
            type="date"
            value={dateTo}
            onChange={(e) => {
              setDateTo(e.target.value);
              resetOffset();
            }}
            className={inputCls}
          />
        </label>
        <button
          type="button"
          onClick={() => {
            setUserQuery(userDraft.trim());
            resetOffset();
          }}
          className="rounded bg-osap-accent px-4 py-1 text-sm text-white"
        >
          {t("adminPayments.filter")}
        </button>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      <div className="overflow-x-auto rounded-lg border border-osap-border">
        <table className="w-full text-left text-sm">
          <thead className="bg-osap-surface text-xs uppercase text-osap-muted">
            <tr>
              <th className="px-3 py-2">{t("adminPayments.date")}</th>
              <th className="px-3 py-2">{t("adminPayments.user")}</th>
              <th className="px-3 py-2">{t("adminPayments.email")}</th>
              <th className="px-3 py-2 text-right">{t("adminPayments.amount")}</th>
              <th className="px-3 py-2">{t("adminPayments.charge")}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-osap-border">
            {loading ? (
              <tr>
                <td colSpan={5} className="px-3 py-8 text-center text-osap-muted">
                  …
                </td>
              </tr>
            ) : items.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-3 py-8 text-center text-osap-muted">
                  {t("adminPayments.emptyDonations")}
                </td>
              </tr>
            ) : (
              items.map((d) => (
                <tr key={d.id} className="odd:bg-osap-bg">
                  <td className="px-3 py-2 text-xs">{formatDate(d.donated_at)}</td>
                  <td className="px-3 py-2">
                    <UserCell userId={d.user_id} />
                  </td>
                  <td className="px-3 py-2 text-xs">{d.email_receipt || "—"}</td>
                  <td className="px-3 py-2 text-right">
                    {formatMoney(d.amount_minor, d.currency)}
                  </td>
                  <td className="px-3 py-2 font-mono text-xs text-osap-muted" title={d.charge_id}>
                    {shortUser(d.charge_id)}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <Pagination
        total={total}
        offset={offset}
        onPrev={() => setOffset((o) => Math.max(0, o - LIMIT))}
        onNext={() => setOffset((o) => o + LIMIT)}
        disabled={loading}
      />
    </div>
  );
}

export function AdminPaymentsPage() {
  const { t } = useI18n();
  const accessToken = useAuth((s) => s.accessToken);
  const [tab, setTab] = useState<Tab>("memberships");

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">{t("admin.paymentsTitle")}</h1>
      <div className="flex gap-1 border-b border-osap-border">
        <button
          type="button"
          onClick={() => setTab("memberships")}
          className={`rounded-t px-4 py-2 text-sm ${
            tab === "memberships"
              ? "border-b-2 border-osap-accent text-osap-accent"
              : "text-osap-muted hover:text-osap-ink"
          }`}
        >
          {t("adminPayments.tabMemberships")}
        </button>
        <button
          type="button"
          onClick={() => setTab("donations")}
          className={`rounded-t px-4 py-2 text-sm ${
            tab === "donations"
              ? "border-b-2 border-osap-accent text-osap-accent"
              : "text-osap-muted hover:text-osap-ink"
          }`}
        >
          {t("adminPayments.tabDonations")}
        </button>
      </div>
      {accessToken ? (
        tab === "memberships" ? (
          <MembershipsTab token={accessToken} />
        ) : (
          <DonationsTab token={accessToken} />
        )
      ) : (
        <p className="text-sm text-red-600">{t("adminPayments.loadError")}</p>
      )}
    </div>
  );
}
