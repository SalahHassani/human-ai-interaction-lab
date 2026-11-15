"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  apiRequest,
  getResearcherToken,
  setResearcherToken,
} from "@/lib/api";

interface ExperimentSummary {
  id: string;
  title: string;
  description: string;
  status: string;
  current_version_id: string | null;
  updated_at: string;
}

export default function DashboardPage() {
  const router = useRouter();
  const [experiments, setExperiments] = useState<ExperimentSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [showCreate, setShowCreate] = useState(false);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [participantInfo, setParticipantInfo] = useState(
    "You are invited to take part in a short human–AI interaction study. Your responses are stored pseudonymously."
  );

  async function loadExperiments() {
    const token = getResearcherToken();
    if (!token) {
      router.push("/login");
      return;
    }
    try {
      const list = await apiRequest<ExperimentSummary[]>(
        "/experiments",
        {},
        token
      );
      setExperiments(list);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load studies");
      setResearcherToken(null);
      router.push("/login");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadExperiments();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    const token = getResearcherToken();
    if (!token) return;
    setError(null);
    try {
      const created = await apiRequest<{ id: string }>(
        "/experiments",
        {
          method: "POST",
          body: JSON.stringify({
            title,
            description,
            participant_information: participantInfo,
          }),
        },
        token
      );
      router.push(`/experiments/${created.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create study");
    }
  }

  function handleLogout() {
    setResearcherToken(null);
    router.push("/login");
  }

  if (loading) {
    return <p className="text-sm text-slate-500">Loading researcher workspace...</p>;
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">
            Researcher Experiments
          </h1>
          <p className="text-sm text-slate-500">
            Manage study conditions, publish immutable versions, and inspect
            participant telemetry.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => setShowCreate(!showCreate)}
            className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-800"
          >
            {showCreate ? "Cancel" : "+ New Experiment"}
          </button>
          <button
            type="button"
            onClick={handleLogout}
            className="rounded-lg border border-slate-300 bg-white px-3.5 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Sign Out
          </button>
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {showCreate && (
        <form
          onSubmit={handleCreate}
          className="space-y-4 rounded-xl border border-slate-200 bg-white p-6 shadow-sm"
        >
          <h2 className="text-lg font-semibold text-slate-900">
            Create Draft Experiment
          </h2>
          <div>
            <label className="block text-sm font-medium text-slate-700">
              Study Title
            </label>
            <input
              type="text"
              required
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g., Confidence Calibration in AI Explanations"
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700">
              Internal Description
            </label>
            <textarea
              rows={2}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700">
              Participant Information Sheet
            </label>
            <textarea
              rows={3}
              required
              value={participantInfo}
              onChange={(e) => setParticipantInfo(e.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            />
          </div>
          <button
            type="submit"
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500"
          >
            Create Study
          </button>
        </form>
      )}

      <div className="grid gap-4">
        {experiments.length === 0 ? (
          <div className="rounded-xl border border-dashed border-slate-300 bg-white p-8 text-center text-sm text-slate-500">
            No experiments yet. Click &ldquo;+ New Experiment&rdquo; to create your
            first study.
          </div>
        ) : (
          experiments.map((exp) => (
            <Link
              key={exp.id}
              href={`/experiments/${exp.id}`}
              className="block rounded-xl border border-slate-200 bg-white p-6 transition hover:border-slate-400"
            >
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h2 className="text-lg font-semibold text-slate-900">
                    {exp.title}
                  </h2>
                  <p className="mt-1 text-sm text-slate-600">
                    {exp.description || "No description provided."}
                  </p>
                </div>
                <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-slate-700">
                  {exp.status}
                </span>
              </div>
              <p className="mt-3 text-xs text-slate-400">
                Last updated: {new Date(exp.updated_at).toLocaleString()}
              </p>
            </Link>
          ))
        )}
      </div>
    </div>
  );
}