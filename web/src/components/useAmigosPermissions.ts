import { useEffect, useState } from "react";
import { apiClient } from "../api/ApiClient";
import type { AmigosMyPermissions } from "../api/types";
import { useAuth } from "../state/auth";

// Permisos del usuario en «Los amigos» (grupos/eventos/blog). Permite mostrar botones de
// edición en la ZONA DE USUARIO sin pasar por el menú Admin. La autorización real la aplica
// el servidor; esto es solo para presentación.
export function useAmigosPermissions(): AmigosMyPermissions | null {
  const user = useAuth((s) => s.user);
  const [perms, setPerms] = useState<AmigosMyPermissions | null>(null);

  useEffect(() => {
    if (user === null) {
      setPerms(null);
      return;
    }
    let cancelled = false;
    apiClient
      .getAmigosMyPermissions()
      .then((p) => {
        if (!cancelled) setPerms(p);
      })
      .catch(() => {
        if (!cancelled) setPerms(null);
      });
    return () => {
      cancelled = true;
    };
  }, [user]);

  return perms;
}
