/** Traduce la selección de macro-familias del bloque Género al contrato real:
 *  ninguna seleccionada = sin filtro (genres ausente); alguna seleccionada = [nombres];
 *  todas las familias seleccionadas = sin filtro (equivale a "cualquier género"). */
export function genresToSearch(
  selected: Record<string, boolean>,
  options: string[],
): string[] | undefined {
  const chosen = options.filter((o) => selected[o]);
  if (chosen.length === 0 || chosen.length === options.length) return undefined;
  return chosen;
}
