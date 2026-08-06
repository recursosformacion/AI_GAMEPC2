import type { ReactNode } from "react";
import { ApiError } from "../api/errors";

// Uniform error representation (code / message / details). No custom formats.
export function EnvelopeError({ error }: { error: ApiError }): ReactNode {
  return (
    <div data-testid="error" className="rounded border border-osap-danger/30 bg-osap-danger/5 p-3 text-osap-danger">
      <p className="font-medium">
        {error.code}: {error.message}
      </p>
      {Object.keys(error.details).length > 0 ? (
        <pre className="mt-1 text-xs">{JSON.stringify(error.details, null, 2)}</pre>
      ) : null}
    </div>
  );
}
