import { useI18n } from "../i18n/I18n";

export function RatingView({ rating, voteCount }: { rating: number | null; voteCount: number }) {
  const { t } = useI18n();
  if (rating === null) {
    return <span className="text-sm text-osap-muted">{t("valuation.none")}</span>;
  }
  return (
    <span className="text-sm text-osap-ink">
      ★ {rating.toFixed(2)} · {voteCount} {t("valuation.votes")}
    </span>
  );
}
