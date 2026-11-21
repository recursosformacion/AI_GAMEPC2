import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  get: vi.fn(),
  completeOidc: vi.fn(),
}));

vi.mock("../api/ApiClient", () => ({
  apiClient: { get: mocks.get },
}));
vi.mock("../i18n/I18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));
vi.mock("../state/auth", () => ({
  useAuth: {
    getState: () => ({ completeOidc: mocks.completeOidc }),
  },
}));

import { useOidcLogin } from "./useOidcLogin";

// jsdom no siempre conserva el WindowProxy simulado al construir MessageEvent.
// Definimos source explícitamente para que las pruebas verifiquen la identidad real
// de la ventana emisora, y no pasen por rechazar accidentalmente source=null.
function createOidcMessageEvent(
  source: WindowProxy,
  origin: string,
  data: Record<string, string>,
) {
  const event = new MessageEvent("message", { origin, data });
  Object.defineProperty(event, "source", { configurable: true, value: source });
  return event;
}

describe("useOidcLogin", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.get.mockResolvedValue({
      configured: true,
      authorize_url: "https://auth.openmusicrepository.com/authorize",
    });
  });

  async function startWithPopup(onDone?: () => void) {
    const popup = {
      location: { assign: vi.fn() },
    } as unknown as WindowProxy;
    vi.spyOn(window, "open").mockReturnValue(popup);

    const hook = renderHook(() => useOidcLogin(onDone));
    await act(async () => {
      expect(await hook.result.current.start()).toBe(true);
    });
    expect(window.open).toHaveBeenCalledOnce();
    return { ...hook, popup };
  }

  it("ignora mensajes de otro origen aunque procedan del popup", async () => {
    const { popup } = await startWithPopup();

    act(() => {
      window.dispatchEvent(
        createOidcMessageEvent(popup, "https://attacker.example", {
          type: "osap-oidc",
          access_token: "attacker-access",
          refresh_token: "attacker-refresh",
        }),
      );
    });

    expect(mocks.completeOidc).not.toHaveBeenCalled();
  });

  it("ignora mensajes del origen correcto si no proceden del popup abierto", async () => {
    await startWithPopup();

    act(() => {
      window.dispatchEvent(
        createOidcMessageEvent(window as unknown as WindowProxy, window.location.origin, {
          type: "osap-oidc",
          access_token: "attacker-access",
          refresh_token: "attacker-refresh",
        }),
      );
    });

    expect(mocks.completeOidc).not.toHaveBeenCalled();
  });

  it("acepta el resultado únicamente del popup y del mismo origen", async () => {
    const onDone = vi.fn();
    const { popup } = await startWithPopup(onDone);

    act(() => {
      window.dispatchEvent(
        createOidcMessageEvent(popup, window.location.origin, {
          type: "osap-oidc",
          access_token: "valid-access",
          refresh_token: "valid-refresh",
        }),
      );
    });

    expect(mocks.completeOidc).toHaveBeenCalledWith("valid-access", "valid-refresh");
    expect(onDone).toHaveBeenCalledOnce();
  });
});
