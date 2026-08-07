import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";
import App from "./App";
import { usePreferences } from "./state/preferences";

describe("Internationalization (V3.4)", () => {
  afterEach(() => {
    usePreferences.getState().setLang("en");
    localStorage.clear();
  });

  it("switches the UI language (es)", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/"]}>
        <App />
      </MemoryRouter>,
    );
    expect(screen.getByRole("link", { name: "Home" })).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("language"), "es");
    expect(screen.getByRole("link", { name: "Inicio" })).toBeInTheDocument();
  });
});
