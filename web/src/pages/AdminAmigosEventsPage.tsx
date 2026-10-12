import { useCallback, useEffect, useState } from "react";
import { apiClient } from "../api/ApiClient";
import type { AmigosEvent, AmigosEventInput, AmigosEventList } from "../api/types";
import { Card } from "../components/Card";
import { useI18n } from "../i18n/I18n";
import type { TKey } from "../i18n/translations";

const KIND_KEY: Record<string, TKey> = {
  concert: "friends.eventKind.concert",
  meeting: "friends.eventKind.meeting",
  festival: "friends.eventKind.festival",
  workshop: "friends.eventKind.workshop",
  mass: "friends.eventKind.mass",
  competition: "friends.eventKind.competition",
  rehearsal: "friends.eventKind.rehearsal",
  other: "friends.eventKind.other",
};
const STATUS_KEY: Record<string, TKey> = {
  draft: "friends.status.draft",
  pending: "friends.status.pending",
  published: "friends.status.published",
  withdrawn: "friends.status.withdrawn",
};

type Form = Partial<AmigosEventInput>;

export function AdminAmigosEventsPage() {
  const { t } = useI18n();
  const [events, setEvents] = useState<AmigosEvent[]>([]);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<Form>({ kind: "concert", modality: "onsite", event_status: "scheduled" });
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await apiClient.get<AmigosEventList>("/admin/amigos/events");
      setEvents(data.items);
    } catch {
      setEvents([]);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const set = (patch: Form) => setForm((prev) => ({ ...prev, ...patch }));

  const reset = () => {
    setEditingId(null);
    setForm({ kind: "concert", modality: "onsite", event_status: "scheduled" });
    setError(null);
  };

  const startEdit = (e: AmigosEvent) => {
    setEditingId(e.id);
    setError(null);
    setForm({
      title: e.title, kind: e.kind, modality: e.modality, event_status: e.event_status,
      starts_on: e.starts_on, starts_at: e.starts_at ?? "", ends_on: e.ends_on ?? "",
      venue_name: e.venue_name ?? "", locality: e.locality ?? "", region: e.region ?? "",
      country_code: e.country_code ?? "", organizer_name: e.organizer_name ?? "",
      organizer_website: e.organizer_website ?? "", event_url: e.event_url ?? "",
      tickets_url: e.tickets_url ?? "", price: e.price ?? "", summary: e.summary ?? "",
      description: e.description ?? "",
    });
  };

  const save = async (action: "draft" | "publish") => {
    setError(null);
    if (!form.title || !form.starts_on) {
      setError(t("friends.titleRequired"));
      return;
    }
    try {
      if (editingId === null) {
        await apiClient.createAmigosEvent({ ...form, title: form.title, starts_on: form.starts_on, action });
      } else {
        await apiClient.updateAmigosEvent(editingId, form);
      }
      reset();
      await load();
    } catch {
      setError(t("friends.errorSaving"));
    }
  };

  const status = async (id: string, value: string) => {
    try {
      await apiClient.setAmigosEventStatus(id, value);
      await load();
    } catch {
      setError(t("friends.errorSaving"));
    }
  };

  const field = (key: keyof AmigosEventInput) => ({
    value: (form[key] ?? "") as string,
    onChange: (ev: React.ChangeEvent<HTMLInputElement>) => set({ [key]: ev.target.value } as Form),
    className: "mt-1 w-full rounded-md border border-osap-border bg-osap-surface px-3 py-2 text-sm",
  });

  return (
    <div className="mx-auto max-w-5xl space-y-4">
      <h1 className="text-xl font-semibold">
        {t("nav.sectionFriends")} · {t("friends.eventsTitle")}
      </h1>

      <Card title={editingId === null ? t("friends.newEvent") : t("friends.edit")}>
        {error ? <p className="mb-2 text-sm text-osap-danger">{error}</p> : null}
        <div className="grid gap-2 sm:grid-cols-3">
          <label className="text-xs text-osap-muted sm:col-span-3">
            {t("friends.titleField")} *
            <input {...field("title")} />
          </label>
          <label className="text-xs text-osap-muted">
            {t("friends.kind")}
            <select value={form.kind ?? "concert"} onChange={(e) => set({ kind: e.target.value })} className="mt-1 w-full rounded-md border border-osap-border bg-osap-surface px-3 py-2 text-sm">
              {Object.entries(KIND_KEY).map(([code, key]) => (<option key={code} value={code}>{t(key)}</option>))}
            </select>
          </label>
          <label className="text-xs text-osap-muted">
            {t("friends.eventDate")} *
            <input type="date" value={form.starts_on ?? ""} onChange={(e) => set({ starts_on: e.target.value })} className="mt-1 w-full rounded-md border border-osap-border bg-osap-surface px-3 py-2 text-sm" />
          </label>
          <label className="text-xs text-osap-muted">
            {t("friends.eventTime")}
            <input type="time" value={(form.starts_at as string) ?? ""} onChange={(e) => set({ starts_at: e.target.value })} className="mt-1 w-full rounded-md border border-osap-border bg-osap-surface px-3 py-2 text-sm" />
          </label>
          <label className="text-xs text-osap-muted">{t("friends.locality")}<input {...field("locality")} /></label>
          <label className="text-xs text-osap-muted">{t("friends.venue")}<input {...field("venue_name")} /></label>
          <label className="text-xs text-osap-muted">{t("friends.country")}<input maxLength={2} {...field("country_code")} /></label>
          <label className="text-xs text-osap-muted">{t("friends.eventOrganizer")}<input {...field("organizer_name")} /></label>
          <label className="text-xs text-osap-muted">{t("friends.eventInfoUrl")}<input {...field("event_url")} /></label>
          <label className="text-xs text-osap-muted">{t("friends.eventTicketsUrl")}<input {...field("tickets_url")} /></label>
          <label className="text-xs text-osap-muted sm:col-span-3">{t("friends.summaryField")}<input {...field("summary")} /></label>
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          <button type="button" onClick={() => void save("draft")} className="rounded-md border border-osap-border px-4 py-2 text-sm">
            {t("friends.saveDraft")}
          </button>
          <button type="button" onClick={() => void save("publish")} className="rounded-md bg-osap-accent px-4 py-2 text-sm font-medium text-white">
            {t("friends.publish")}
          </button>
          {editingId !== null ? (
            <button type="button" onClick={reset} className="rounded-md border border-osap-border px-4 py-2 text-sm">
              {t("adminUsers.cancel")}
            </button>
          ) : null}
        </div>
      </Card>

      <div className="overflow-x-auto rounded border border-osap-border bg-osap-surface">
        <table className="w-full text-sm">
          <thead className="border-b border-osap-border text-left">
            <tr>
              <th className="px-3 py-2">{t("friends.titleField")}</th>
              <th className="px-3 py-2">{t("friends.eventDate")}</th>
              <th className="px-3 py-2">{t("friends.kind")}</th>
              <th className="px-3 py-2">{t("friends.active")}</th>
              <th className="px-3 py-2 text-right">{t("adminUsers.actions")}</th>
            </tr>
          </thead>
          <tbody>
            {events.map((e) => (
              <tr key={e.id} className="border-b border-osap-border last:border-0">
                <td className="px-3 py-2">{e.title}</td>
                <td className="px-3 py-2">{e.starts_on}</td>
                <td className="px-3 py-2">{t(KIND_KEY[e.kind] ?? "friends.eventKind.other")}</td>
                <td className="px-3 py-2">{t(STATUS_KEY[e.editorial_status] ?? "friends.status.draft")}</td>
                <td className="px-3 py-2">
                  <div className="flex flex-wrap items-center justify-end gap-2 text-xs">
                    <button type="button" onClick={() => startEdit(e)} className="text-osap-accent hover:underline">
                      {t("friends.edit")}
                    </button>
                    {e.editorial_status === "pending" ? (
                      <button type="button" onClick={() => void status(e.id, "published")} className="text-osap-success hover:underline">
                        {t("friends.approve")}
                      </button>
                    ) : e.editorial_status === "draft" ? (
                      <button type="button" onClick={() => void status(e.id, "pending")} className="text-osap-accent hover:underline">
                        {t("friends.submit")}
                      </button>
                    ) : e.editorial_status === "published" ? (
                      <button type="button" onClick={() => void status(e.id, "withdrawn")} className="text-osap-danger hover:underline">
                        {t("friends.deactivate")}
                      </button>
                    ) : null}
                  </div>
                </td>
              </tr>
            ))}
            {events.length === 0 ? (
              <tr><td colSpan={5} className="px-3 py-4 text-center text-osap-muted">{t("friends.eventsEmpty")}</td></tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </div>
  );
}
