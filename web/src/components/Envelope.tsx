import type { ReactNode } from "react";
import { ApiError } from "../api/errors";
import { EmptyState } from "./EmptyState";
import { EnvelopeError } from "./EnvelopeError";
import { Loading } from "./Loading";

// The four interface states: Loading / Ready / Empty / Error. Ready is delegated to `children`.
export interface EnvelopeProps<T> {
  loading: boolean;
  error: ApiError | null;
  data: T | null;
  isEmpty?: (data: T) => boolean;
  loadingLabel?: string;
  emptyMessage?: string;
  children: (data: T) => ReactNode;
}

const defaultEmpty = <T,>(data: T): boolean => Array.isArray(data) && data.length === 0;

export function Envelope<T>({
  loading,
  error,
  data,
  isEmpty = defaultEmpty,
  loadingLabel,
  emptyMessage,
  children,
}: EnvelopeProps<T>): ReactNode {
  if (loading) {
    return <Loading label={loadingLabel} />;
  }
  if (error !== null) {
    return <EnvelopeError error={error} />;
  }
  if (data === null || isEmpty(data)) {
    return <EmptyState message={emptyMessage} />;
  }
  return <>{children(data)}</>;
}
