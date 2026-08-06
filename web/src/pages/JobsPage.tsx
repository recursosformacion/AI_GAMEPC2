import { useEffect, useState } from "react";
import { Button } from "../components/Button";
import { Envelope } from "../components/Envelope";
import { ResultList } from "../components/ResultList";
import { useJobs } from "../state/jobs";

export function JobsPage() {
  const { data, loading, error, list, create } = useJobs();
  const [type, setType] = useState("provider-sync");

  useEffect(() => {
    void list();
  }, [list]);

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    void create(type);
  };

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Jobs</h1>
      <form onSubmit={submit} className="flex flex-wrap items-end gap-2">
        <label className="flex flex-col text-sm">
          Type
          <input
            aria-label="job-type"
            value={type}
            onChange={(e) => setType(e.target.value)}
            className="mt-1 rounded border border-osap-border px-2 py-1"
          />
        </label>
        <Button type="submit">Create job</Button>
      </form>
      <Envelope loading={loading} error={error} data={data} emptyMessage="No jobs">
        {(jobs) => (
          <ResultList
            items={jobs}
            keyOf={(j) => j.job_id}
            renderItem={(j) => (
              <span>
                {j.job_id} · {j.type} · {j.state} · {j.progress}%
              </span>
            )}
          />
        )}
      </Envelope>
    </div>
  );
}
