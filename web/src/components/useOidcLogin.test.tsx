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
    } as unknown as Window;
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
        new MessageEvent("message", {
          origin: "https://attacker.example",
          source: popup,
          data: {
            type: "osap-oidc",
            access_token: "attacker-access",
            refresh_token: "attacker-refresh",
          },
        }),
      );
    });

    expect(mocks.completeOidc).not.toHaveBeenCalled();
  });

  it("ignora mensajes del origen correcto si no proceden del popup abierto", async () => {
    await startWithPopup();

    act(() => {
      window.dispatchEvent(
        new MessageEvent("message", {
          origin: window.location.origin,
          source: window,
          data: {
            type: "osap-oidc",
            access_token: "attacker-access",
            refresh_token: "attacker-refresh",
          },
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
        new MessageEvent("message", {
          origin: window.location.origin,
          source: popup,
          data: {
            type: "osap-oidc",
            access_token: "valid-access",
            refresh_token: "valid-refresh",
          },
        }),
      );
    });

    expect(mocks.completeOidc).toHaveBeenCalledWith("valid-access", "valid-refresh");
    expect(onDone).toHaveBeenCalledOnce();
  });
});
