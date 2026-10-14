// Utilidades de fecha. El sitio muestra las fechas en formato europeo (dd/mm/aaaa).

/** Formatea una fecha ISO (`AAAA-MM-DD`, con o sin hora) como `dd/mm/aaaa`. */
export function formatEuroDate(value: string | null | undefined): string {
  if (value === null || value === undefined || value === "") return "";
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value);
  if (match === null) return value;
  return `${match[3]}/${match[2]}/${match[1]}`;
}
