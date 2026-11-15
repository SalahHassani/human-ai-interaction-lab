"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  apiRequest,
  downloadExperimentCsv,
  getResearcherToken,
} from "@/lib/api";

interface TaskItem {
  id: string;
  title: string;
  instructions: string;
  task_order: number;
}

interface ConditionItem {
  id: string;
  name: string;
  description: string;
  ai_answer_template: string;
  ai_explanation_template: string | null;
  condition_order: number;
  tasks: TaskItem[];
}

interface VersionItem {
  id: string;
  version_number: number;
  published_at: string;
}

interface ExperimentDetail {
  id: string;
  title: string;
  description: string;
  participant_information: string;
  consent_statement: string;
  status: string;
  current_version_id: string | null;
  draft_conditions: ConditionItem[];
  versions: VersionItem[];
}

interface InvitationItem {
  id: string;
  label: string;
  expires_at: string;
  max_uses: number | null;
  use_count: number;
}

interface AnalyticsData {
  funnel: {
    total_opened: number;
    consented_count: number;
    declined_count: number;
    assigned_count: number;
    completed_count: number;
    incomplete_count: number;
    completion_rate: number;
  };
  condition_balance: {
    condition_id: string;
    condition_name: string;
    version_number: number;
    assigned_count: number;
    completed_count: number;
  }[];
  rating_summaries: {
    condition_id: string;
    condition_name: string;
    question_id: string;
    n: number;
    mean: number | null;
    median: number | null;
    sd: number | null;
    min: number | null;
    max: number | null;
  }[];
  median_completion_seconds: number | null;
  data_quality_flags: {
    participant_code: string | null;
    flag_code: string;
    severity: string;
    details: string;
  }[];
}

const DEFAULT_LIKERT_QUESTIONS = [
  {
    id: "trust_rating",
    label: "I trust the AI system's recommendation.",
    type: "likert",
    min: 1,
    max: 7,
    required: true,
  },
  {
    id: "confidence_rating",
    label: "I feel confident in my final decision.",
    type: "likert",
    min: 1,
    max: 7,
    required: true,
  },
  {
    id: "usefulness_rating",
    label: "The AI response was useful for completing this task.",
    type: "likert",
    min: 1,
    max: 7,
    required: true,
  },
];

export default function ExperimentStudioPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const expId = params.id;

  const [tab, setTab] = useState<"design" | "recruitment" | "analytics">(
    "design"
  );
  const [experiment, setExperiment] = useState<ExperimentDetail | null>(null);
  const [invitations, setInvitations] = useState<InvitationItem[]>([]);
  const [analytics, setAnalytics] = useState<AnalyticsData | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Condition form state
  const [condName, setCondName] = useState("");
  const [condDesc, setCondDesc] = useState("");
  const [aiAnswer, setAiAnswer] = useState("");
  const [aiExplanation, setAiExplanation] = useState("");

  // Task form state
  const [targetCondId, setTargetCondId] = useState("");
  const [taskTitle, setTaskTitle] = useState("");
  const [taskInstructions, setTaskInstructions] = useState("");
  const [scenarioPrompt, setScenarioPrompt] = useState("");

  // Invitation form state
  const [inviteLabel, setInviteLabel] = useState("Participant Cohort");
  const [latestInviteUrl, setLatestInviteUrl] = useState<string | null>(null);

  async function refreshAll() {
    const token = getResearcherToken();
    if (!token) {
      router.push("/login");
      return;
    }
    try {
      const [expData, invData, anData] = await Promise.all([
        apiRequest<ExperimentDetail>(`/experiments/${expId}`, {}, token),
        apiRequest<InvitationItem[]>(
          `/experiments/${expId}/invitations`,
          {},
          token
        ),
        apiRequest<AnalyticsData>(`/experiments/${expId}/analytics`, {}, token),
      ]);
      setExperiment(expData);
      setInvitations(invData);
      setAnalytics(anData);
      if (!targetCondId && expData.draft_conditions.length > 0) {
        setTargetCondId(expData.draft_conditions[0].id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load study");
    }
  }

  useEffect(() => {
    refreshAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [expId]);

  async function handleAddCondition(e: React.FormEvent) {
    e.preventDefault();
    const token = getResearcherToken();
    if (!token || !experiment) return;
    setError(null);
    setNotice(null);
    try {
      await apiRequest(
        `/experiments/${expId}/conditions`,
        {
          method: "POST",
          body: JSON.stringify({
            name: condName,
            description: condDesc,
            ai_answer_template: aiAnswer,
            ai_explanation_template: aiExplanation.trim() || null,
            condition_order: experiment.draft_conditions.length + 1,
          }),
        },
        token
      );
      setCondName("");
      setCondDesc("");
      setAiAnswer("");
      setAiExplanation("");
      setNotice("Condition added to draft.");
      await refreshAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add condition");
    }
  }

  async function handleAddTask(e: React.FormEvent) {
    e.preventDefault();
    const token = getResearcherToken();
    if (!token) return;
    setError(null);
    setNotice(null);
    try {
      await apiRequest(
        `/experiments/${expId}/tasks`,
        {
          method: "POST",
          body: JSON.stringify({
            condition_id: targetCondId,
            title: taskTitle,
            instructions: taskInstructions,
            scenario_prompt: scenarioPrompt,
            task_order: 1,
            questions_json: DEFAULT_LIKERT_QUESTIONS,
          }),
        },
        token
      );
      setTaskTitle("");
      setTaskInstructions("");
      setScenarioPrompt("");
      setNotice("Task attached to condition.");
      await refreshAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add task");
    }
  }

  async function handlePublish() {
    const token = getResearcherToken();
    if (!token) return;
    setError(null);
    setNotice(null);
    try {
      const ver = await apiRequest<{ version_number: number }>(
        `/experiments/${expId}/publish`,
        { method: "POST" },
        token
      );
      setNotice(`Published immutable Version v${ver.version_number}!`);
      await refreshAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Publish failed");
    }
  }

  async function handleCreateInvite(e: React.FormEvent) {
    e.preventDefault();
    const token = getResearcherToken();
    if (!token) return;
    setError(null);
    try {
      const res = await apiRequest<{ invite_url: string }>(
        `/experiments/${expId}/invitations`,
        {
          method: "POST",
          body: JSON.stringify({ label: inviteLabel, expires_in_hours: 168 }),
        },
        token
      );
      setLatestInviteUrl(res.invite_url);
      await refreshAll();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Could not generate invitation"
      );
    }
  }

  if (!experiment) {
    return <p className="text-sm text-slate-500">Loading study studio...</p>;
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4 rounded-xl border border-slate-200 bg-white p-6">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-slate-900">
              {experiment.title}
            </h1>
            <span className="rounded-full bg-indigo-50 px-3 py-1 text-xs font-semibold uppercase text-indigo-700">
              {experiment.status}
            </span>
          </div>
          <p className="mt-1 text-sm text-slate-600">{experiment.description}</p>
          <p className="mt-2 text-xs text-slate-400">
            Published Versions:{" "}
            {experiment.versions.length > 0
              ? experiment.versions
                  .map((v) => `v${v.version_number}`)
                  .join(", ")
              : "None yet"}
          </p>
        </div>

        <button
          type="button"
          onClick={handlePublish}
          className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-500"
        >
          Publish Immutable Version
        </button>
      </div>

      {notice && (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
          {notice}
        </div>
      )}
      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Navigation Tabs */}
      <div className="flex gap-2 border-b border-slate-200">
        {(["design", "recruitment", "analytics"] as const).map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t)}
            className={`border-b-2 px-4 py-2.5 text-sm font-semibold capitalize transition ${
              tab === t
                ? "border-slate-900 text-slate-900"
                : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            {t === "analytics" ? "Analytics & CSV Exports" : t}
          </button>
        ))}
      </div>

      {/* DESIGN TAB */}
      {tab === "design" && (
        <div className="space-y-6">
          <div className="grid gap-4 md:grid-cols-2">
            {experiment.draft_conditions.map((c) => (
              <div
                key={c.id}
                className="rounded-xl border border-slate-200 bg-white p-5"
              >
                <div className="flex items-center justify-between">
                  <h3 className="font-semibold text-slate-900">{c.name}</h3>
                  <span className="text-xs text-slate-400">
                    Order #{c.condition_order}
                  </span>
                </div>
                <p className="mt-1 text-xs text-slate-500">{c.description}</p>
                <div className="mt-3 rounded-lg bg-slate-50 p-3 text-xs text-slate-700">
                  <p className="font-semibold">AI Answer Template:</p>
                  <p className="mt-0.5">{c.ai_answer_template}</p>
                  {c.ai_explanation_template && (
                    <>
                      <p className="mt-2 font-semibold">
                        AI Explanation Template:
                      </p>
                      <p className="mt-0.5">{c.ai_explanation_template}</p>
                    </>
                  )}
                </div>
                <div className="mt-3">
                  <p className="text-xs font-semibold text-slate-600">
                    Tasks ({c.tasks.length}):
                  </p>
                  <ul className="mt-1 list-inside list-disc text-xs text-slate-600">
                    {c.tasks.map((t) => (
                      <li key={t.id}>{t.title}</li>
                    ))}
                  </ul>
                </div>
              </div>
            ))}
          </div>

          <div className="grid gap-6 md:grid-cols-2">
            <form
              onSubmit={handleAddCondition}
              className="space-y-3 rounded-xl border border-slate-200 bg-white p-5"
            >
              <h3 className="font-semibold text-slate-900">
                Add Experimental Condition
              </h3>
              <input
                type="text"
                required
                placeholder="Condition Name (e.g., Condition C: High Uncertainty)"
                value={condName}
                onChange={(e) => setCondName(e.target.value)}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              />
              <input
                type="text"
                placeholder="Short description"
                value={condDesc}
                onChange={(e) => setCondDesc(e.target.value)}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              />
              <textarea
                required
                rows={2}
                placeholder="Fixed AI Answer Template"
                value={aiAnswer}
                onChange={(e) => setAiAnswer(e.target.value)}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              />
              <textarea
                rows={2}
                placeholder="Optional AI Explanation Template"
                value={aiExplanation}
                onChange={(e) => setAiExplanation(e.target.value)}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              />
              <button
                type="submit"
                className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white"
              >
                Save Condition
              </button>
            </form>

            <form
              onSubmit={handleAddTask}
              className="space-y-3 rounded-xl border border-slate-200 bg-white p-5"
            >
              <h3 className="font-semibold text-slate-900">
                Add Task to Condition
              </h3>
              <select
                value={targetCondId}
                onChange={(e) => setTargetCondId(e.target.value)}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              >
                {experiment.draft_conditions.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
              <input
                type="text"
                required
                placeholder="Task Title"
                value={taskTitle}
                onChange={(e) => setTaskTitle(e.target.value)}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              />
              <textarea
                rows={2}
                required
                placeholder="Participant instructions"
                value={taskInstructions}
                onChange={(e) => setTaskInstructions(e.target.value)}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              />
              <textarea
                rows={2}
                required
                placeholder="Decision scenario prompt"
                value={scenarioPrompt}
                onChange={(e) => setScenarioPrompt(e.target.value)}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              />
              <button
                type="submit"
                className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white"
              >
                Add Task
              </button>
            </form>
          </div>
        </div>
      )}

      {/* RECRUITMENT TAB */}
      {tab === "recruitment" && (
        <div className="space-y-6">
          <form
            onSubmit={handleCreateInvite}
            className="flex flex-wrap items-end gap-3 rounded-xl border border-slate-200 bg-white p-5"
          >
            <div className="flex-1">
              <label className="block text-xs font-semibold uppercase text-slate-500">
                Invitation Batch Label
              </label>
              <input
                type="text"
                required
                value={inviteLabel}
                onChange={(e) => setInviteLabel(e.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              />
            </div>
            <button
              type="submit"
              className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-800"
            >
              Generate Participant Link
            </button>
          </form>

          {latestInviteUrl && (
            <div className="rounded-xl border border-indigo-200 bg-indigo-50 p-4 text-sm">
              <p className="font-semibold text-indigo-900">
                New Participant Study Link (copy & open in a browser tab):
              </p>
              <code className="mt-1 block break-all rounded bg-white px-3 py-2 text-xs text-slate-800">
                {latestInviteUrl}
              </code>
            </div>
          )}

          <div className="rounded-xl border border-slate-200 bg-white p-5">
            <h3 className="font-semibold text-slate-900">Issued Invitations</h3>
            <div className="mt-3 divide-y divide-slate-100 text-sm">
              {invitations.map((inv) => (
                <div
                  key={inv.id}
                  className="flex items-center justify-between py-2.5"
                >
                  <div>
                    <p className="font-medium text-slate-800">{inv.label}</p>
                    <p className="text-xs text-slate-400">
                      Expires: {new Date(inv.expires_at).toLocaleString()}
                    </p>
                  </div>
                  <span className="text-xs font-semibold text-slate-600">
                    Uses: {inv.use_count}
                    {inv.max_uses ? ` / ${inv.max_uses}` : ""}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ANALYTICS & EXPORTS TAB */}
      {tab === "analytics" && analytics && (
        <div className="space-y-6">
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <p className="text-xs text-slate-500">Opened Study</p>
              <p className="mt-1 text-2xl font-bold text-slate-900">
                {analytics.funnel.total_opened}
              </p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <p className="text-xs text-slate-500">Consented</p>
              <p className="mt-1 text-2xl font-bold text-slate-900">
                {analytics.funnel.consented_count}
              </p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <p className="text-xs text-slate-500">Completed</p>
              <p className="mt-1 text-2xl font-bold text-emerald-600">
                {analytics.funnel.completed_count}
              </p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <p className="text-xs text-slate-500">Completion Rate</p>
              <p className="mt-1 text-2xl font-bold text-slate-900">
                {analytics.funnel.completion_rate}%
              </p>
            </div>
          </div>

          {/* Condition Balance */}
          <div className="rounded-xl border border-slate-200 bg-white p-5">
            <h3 className="font-semibold text-slate-900">Condition Balance</h3>
            <table className="mt-3 w-full text-left text-sm">
              <thead className="border-b border-slate-200 text-xs uppercase text-slate-500">
                <tr>
                  <th className="py-2">Condition</th>
                  <th className="py-2">Version</th>
                  <th className="py-2">Assigned</th>
                  <th className="py-2">Completed</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {analytics.condition_balance.map((b) => (
                  <tr key={b.condition_id}>
                    <td className="py-2 font-medium">{b.condition_name}</td>
                    <td className="py-2">v{b.version_number}</td>
                    <td className="py-2">{b.assigned_count}</td>
                    <td className="py-2">{b.completed_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Descriptive Rating Summaries */}
          <div className="rounded-xl border border-slate-200 bg-white p-5">
            <h3 className="font-semibold text-slate-900">
              Descriptive Rating Statistics (Likert Scales)
            </h3>
            {analytics.rating_summaries.length === 0 ? (
              <p className="mt-2 text-sm text-slate-500">
                No numeric rating responses collected yet.
              </p>
            ) : (
              <table className="mt-3 w-full text-left text-sm">
                <thead className="border-b border-slate-200 text-xs uppercase text-slate-500">
                  <tr>
                    <th className="py-2">Condition</th>
                    <th className="py-2">Question</th>
                    <th className="py-2">n</th>
                    <th className="py-2">Mean</th>
                    <th className="py-2">Median</th>
                    <th className="py-2">SD</th>
                    <th className="py-2">Min–Max</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {analytics.rating_summaries.map((s) => (
                    <tr key={`${s.condition_id}-${s.question_id}`}>
                      <td className="py-2 font-medium">{s.condition_name}</td>
                      <td className="py-2 font-mono text-xs">{s.question_id}</td>
                      <td className="py-2">{s.n}</td>
                      <td className="py-2">{s.mean ?? "—"}</td>
                      <td className="py-2">{s.median ?? "—"}</td>
                      <td className="py-2">{s.sd ?? "—"}</td>
                      <td className="py-2">
                        {s.min ?? "—"} – {s.max ?? "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          {/* Data Quality Flags */}
          <div className="rounded-xl border border-slate-200 bg-white p-5">
            <h3 className="font-semibold text-slate-900">
              Data Quality Diagnostics ({analytics.data_quality_flags.length})
            </h3>
            {analytics.data_quality_flags.length === 0 ? (
              <p className="mt-2 text-sm text-slate-500">
                No anomalies flagged.
              </p>
            ) : (
              <ul className="mt-2 space-y-2 text-xs">
                {analytics.data_quality_flags.map((f, idx) => (
                  <li
                    key={idx}
                    className="rounded-lg bg-amber-50 px-3 py-2 text-amber-900"
                  >
                    <span className="font-semibold">
                      [{f.flag_code}] {f.participant_code || "Study"}:
                    </span>{" "}
                    {f.details}
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* Safe CSV Exports */}
          <div className="rounded-xl border border-slate-200 bg-white p-5">
            <h3 className="font-semibold text-slate-900">
              Export Analysis-Ready CSV Datasets
            </h3>
            <p className="mt-1 text-xs text-slate-500">
              Pseudonymous, formula-escaped CSV exports with sensitive hashes
              stripped.
            </p>
            <div className="mt-4 flex flex-wrap gap-2">
              {[
                "participants",
                "assignments",
                "responses",
                "messages",
                "events",
                "experiment_summary",
              ].map((ds) => (
                <button
                  key={ds}
                  type="button"
                  onClick={() => {
                    const tok = getResearcherToken();
                    if (tok) downloadExperimentCsv(expId, ds, tok);
                  }}
                  className="rounded-lg border border-slate-300 bg-slate-50 px-3.5 py-2 text-xs font-semibold text-slate-800 hover:bg-slate-100"
                >
                  Download {ds}.csv
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}