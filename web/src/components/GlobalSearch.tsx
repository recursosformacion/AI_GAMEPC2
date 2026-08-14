import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useI18n } from "../i18n/I18n";
import { searchAndGo } from "../state/navigation";
import { useSearches } from "../state/searches";
import { Button } from "./Button";
import { Spinner } from "./Spinner";

export function GlobalSearch() {
  const { t } = useI18n();
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const searching = useSearches((s) => s.loading);

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    if (!query.trim()) return;
    void searchAndGo(navigate, { query, limit: 30 });
  };

  return (
    <form onSubmit={submit} className="flex items-center gap-1" role="search">
      <input
        aria-label="search"
        placeholder={t("search.placeholder")}
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        className="w-40 rounded border border-osap-border bg-osap-surface px-2 py-1 text-sm sm:w-64"
      />
      {searching ? (
        <span className="flex items-center justify-center px-1">
          <Spinner />
        </span>
      ) : (
        <Button type="submit" disabled={!query.trim()}>
          {t("search")}
        </Button>
      )}
    </form>
  );
}
