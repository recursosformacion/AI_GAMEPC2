import { render, screen } from "@testing-library/react";
import { ApiError } from "../api/errors";
import { EmptyState } from "./EmptyState";
import { Envelope } from "./Envelope";
import { EnvelopeError } from "./EnvelopeError";
import { Loading } from "./Loading";
import { ResultList } from "./ResultList";

describe("Envelope — interface states", () => {
  it("renders Loading", () => {
    render(
      <Envelope loading error={null} data={null}>
        {() => null}
      </Envelope>,
    );
    expect(screen.getByTestId("loading")).toBeInTheDocument();
  });

  it("renders Empty for an empty array", () => {
    render(
      <Envelope loading={false} error={null} data={[]}>
        {() => null}
      </Envelope>,
    );
    expect(screen.getByTestId("empty")).toBeInTheDocument();
  });

  it("renders Error via EnvelopeError", () => {
    render(
      <Envelope loading={false} error={new ApiError("INVALID_QUERY", "Query cannot be empty")} data={null}>
        {() => null}
      </Envelope>,
    );
    expect(screen.getByTestId("error")).toHaveTextContent("INVALID_QUERY: Query cannot be empty");
  });

  it("renders Ready through children", () => {
    render(
      <Envelope loading={false} error={null} data={[1, 2]}>
        {(data) => <span>ready {data.length}</span>}
      </Envelope>,
    );
    expect(screen.getByText("ready 2")).toBeInTheDocument();
  });
});

describe("Reusable components", () => {
  it("Loading and EmptyState have stable test ids", () => {
    const { rerender } = render(<Loading />);
    expect(screen.getByTestId("loading")).toBeInTheDocument();
    rerender(<EmptyState />);
    expect(screen.getByTestId("empty")).toBeInTheDocument();
  });

  it("ResultList renders one item per entry", () => {
    render(
      <ResultList
        items={[{ id: "a" }, { id: "b" }]}
        keyOf={(x) => x.id}
        renderItem={(x) => <span>{x.id}</span>}
      />,
    );
    expect(screen.getByText("a")).toBeInTheDocument();
    expect(screen.getByText("b")).toBeInTheDocument();
  });

  it("EnvelopeError shows code, message and details", () => {
    render(<EnvelopeError error={new ApiError("X", "boom", { field: "q" })} />);
    expect(screen.getByText("X: boom")).toBeInTheDocument();
    expect(screen.getByText(/"field": "q"/)).toBeInTheDocument();
  });
});
