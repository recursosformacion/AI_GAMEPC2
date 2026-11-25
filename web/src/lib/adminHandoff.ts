/**
 * Handoff POST de sesión hacia los paneles administrativos externos
 * (osap-storage, osap-support, ai_publicidad).
 *
 * Cómo funciona:
 * 1. El gesto del usuario abre sincrónicamente una ventana vacía (evita el bloqueo de popups).
 * 2. Se pide a osap-api (`POST /api/v1/admin/*-web`) el destino y el token de servicio.
 * 3. Se envía un formulario POST oculto a esa ventana: el token nunca viaja en una URL.
 *
 * Restricciones del receptor: los endpoints de handoff validan el encabezado `Origin`
 * contra una lista de orígenes permitidos. La política de referencia por defecto del
 * navegador (`strict-origin-when-cross-origin`) envía solo el origen en un POST
 * cross-origin, que es justo lo que el receptor necesita.
 */

export interface AdminHandoff {
  url: string;
  token: string;
  next: string;
}

/** Envia el handoff como formulario POST a la ventana `target`. Devuelve false si no se pudo enviar. */
export function submitAdminHandoff(handoff: AdminHandoff, target: string): boolean {
  const form = document.createElement("form");
  form.method = "POST";
  form.action = handoff.url;
  form.target = target;
  form.hidden = true;
  form.style.display = "none";
  for (const [name, value] of Object.entries({ token: handoff.token, next: handoff.next })) {
    const input = document.createElement("input");
    input.type = "hidden";
    input.name = name;
    input.value = value;
    form.appendChild(input);
  }
  document.body.appendChild(form);
  try {
    form.submit();
  } catch {
    return false;
  } finally {
    form.remove();
  }
  return true;
}
