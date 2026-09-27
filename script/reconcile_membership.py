"""Reconciliador de membresía osap-support → overrides donor de osap-api (fase 4.2, paso 5).

Resumen: para cada usuario candidato consulta el endpoint M2M de membresía de osap-support
y materializa/retira el override de cuota (`user_quota_overrides`, 1000/día) con la vigencia
exacta recibida, emitiendo los eventos del funnel. Idempotente y tolerante a fallos: si
support no responde, NO se retira la promoción. Pensado para ejecutarse **cada 15 min**.

Uso (por defecto, dry-run informativo; `--apply` ejecuta):
    python script/reconcile_membership.py --user-id <uuid> [--apply]
    python script/reconcile_membership.py --apply            # candidatos desde la BD

Candidatos (sin `--user-id`): usuarios con eventos de funnel o con override existente.

El service token M2M se pide con `--support-audience` (por defecto `osap-support`), la
audiencia que valida osap-support (`[identity] service_audience`). Vacío = audiencia por
defecto de osap-auth.
"""

from __future__ import annotations

import argparse
import sys

import pymysql
from pymysql.cursors import DictCursor

from src.osap.application.reconcile_membership import ReconcileMembershipUseCase
from src.osap.infrastructure.auth.service_token_provider import ClientCredentialsServiceTokenProvider
from src.osap.infrastructure.state.funnel import build_funnel_store
from src.osap.infrastructure.state.quota import build_quota_store
from src.osap.infrastructure.support import SupportMembershipClient


def _candidates(conn: pymysql.connections.Connection) -> list[str]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT DISTINCT user_id FROM funnel_events WHERE user_id IS NOT NULL "
            "UNION SELECT user_id FROM user_quota_overrides"
        )
        return [str(r["user_id"]) for r in cur.fetchall()]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db-host", default="127.0.0.1")
    ap.add_argument("--db-user", default="osap2027")
    ap.add_argument("--db-password", default="2027osapdb")
    ap.add_argument("--db-api", default="osap-api")
    ap.add_argument("--support-base-url", default="http://127.0.0.1:8300")
    ap.add_argument("--support-client-id", default="osap-api")
    ap.add_argument("--support-client-secret", default="")
    ap.add_argument(
        "--support-audience",
        default="osap-support",
        help="Audiencia del service token M2M que valida osap-support (vacío = por defecto)",
    )
    ap.add_argument("--token-url", default="http://osap-auth/auth-api/oauth/token")
    ap.add_argument("--user-id", action="append", default=[])
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--apply", action="store_true", help="sin esto: dry-run (no escribe)")
    args = ap.parse_args()

    db = {"host": args.db_host, "user": args.db_user, "password": args.db_password,
          "database": args.db_api}
    conn = pymysql.connect(**db, charset="utf8mb4", cursorclass=DictCursor)
    try:
        users = args.user_id or _candidates(conn)
        if args.limit:
            users = users[: args.limit]
        print(f"candidatos: {len(users)}")

        quota = build_quota_store(**db)
        funnel = build_funnel_store(**db)
        if not args.apply:
            # Dry-run: solo informa del estado actual de overrides y candidatos.
            overrides = {str(r["user_id"]) for r in quota.list_overrides()}
            print(f"overrides actuales: {len(overrides)}")
            print("dry-run: usa --apply para reconciliar")
            return 0

        source = SupportMembershipClient(
            base_url=args.support_base_url,
            token_provider=ClientCredentialsServiceTokenProvider(
                client_id=args.support_client_id,
                client_secret=args.support_client_secret,
                token_url=args.token_url,
                audience=args.support_audience or None,
            ),
        )
        uc = ReconcileMembershipUseCase(source=source, quota=quota, funnel=funnel)
        summary = uc.reconcile(users)
        print("resultado:", summary)
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
