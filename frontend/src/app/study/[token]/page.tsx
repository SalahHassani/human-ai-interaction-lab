"use client";

import { Suspense, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { apiRequest } from "@/lib/api";

interface QuestionSpec {
  id: string;
  label: string;
  type: "likert" | "text" | "choice";
  min?: number;
  max?: number;
  required: boolean;
}

interface TaskPublic {
  id: string;
  title: string;
  instructions: string;
  scenario_prompt: string;
  questions_json: QuestionSpec[];
}

interface FlowState {
  step: "consent" | "declined" | "assign" | "tasks" | "completed";
  pseudonymous_code: string;
  experiment_title: string;
  participant_information: string;
  consent_statement: string;
  consented: boolean;
  declined: boolean;
  completed: boolean;
  assignment: {
    condition_id: string;
    condition: {
      id: string;
      name: string;
      description: string;
      tasks: TaskPublic[];
    };
  } | null;
  messages: {
    id: string;
    role: "participant" | "assistant" | "system";
    content: string;
    created_at: string;
  }[];
  submitted_responses: {
    id: string;
    question_id: string;
    value_json: { value: number | string };
  }[];
}

function ParticipantStudyRunnerContent() {
  const params = useParams<{ token: string }>();
  const inviteToken = params.token;

  const [sessionToken, setSessionToken] = useState<string | null>(null);
  const [flow, setFlow] = useState<FlowState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [promptInput, setPromptInput] = useState("");
  const [sendingChat, setSendingChat] = useState(false);
  const [answers, setAnswers] = useState<Record<string, number | string>>({});
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!inviteToken) return;
    async function init() {
      try {
        const storageKey = `hai_participant_${inviteToken}`;
        const saved = localStorage.getItem(storageKey);
        const sess = await apiRequest<{ session_token: string }>(
          "/participant/session",
          {
            method: "POST",
            body: JSON.stringify({
              invite_token: inviteToken,
              existing_session_token: saved,
            }),
          }
        );
        localStorage.setItem(storageKey, sess.session_token);
        setSessionToken(sess.session_token);

        const currentFlow = await apiRequest<FlowState>(
          "/participant/flow",
          {},
          null,
          sess.session_token
        );
        setFlow(currentFlow);
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Invalid invitation link"
        );
      }
    }
    init();
  }, [inviteToken]);

  async function handleConsent(consented: boolean) {
    if (!sessionToken) return;
    setError(null);
    try {
      await apiRequest<FlowState>(
        "/participant/consent",
        {
          method: "POST",
          body: JSON.stringify({ consented }),
        },
        null,
        sessionToken
      );
      if (consented) {
        await apiRequest(
          "/participant/assign",
          { method: "POST" },
          null,
          sessionToken
        );
      }
      const updated = await apiRequest<FlowState>(
        "/participant/flow",
        {},
        null,
        sessionToken
      );
      setFlow(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Consent error");
    }
  }

  async function handleAssign() {
    if (!sessionToken) return;
    await apiRequest(
      "/participant/assign",
      { method: "POST" },
      null,
      sessionToken
    );
    const updated = await apiRequest<FlowState>(
      "/participant/flow",
      {},
      null,
      sessionToken
    );
    setFlow(updated);
  }

  async function handleSendMessage(e: React.FormEvent, taskId: string) {
    e.preventDefault();
    if (!sessionToken || !promptInput.trim()) return;
    setSendingChat(true);
    setError(null);
    try {
      await apiRequest(
        "/participant/messages",
        {
          method: "POST",
          body: JSON.stringify({ task_id: taskId, content: promptInput }),
        },
        null,
        sessionToken
      );
      setPromptInput("");
      const updated = await apiRequest<FlowState>(
        "/participant/flow",
        {},
        null,
        sessionToken
      );
      setFlow(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not send message");
    } finally {
      setSendingChat(false);
    }
  }

  async function handleSubmitRatings(e: React.FormEvent, task: TaskPublic) {
    e.preventDefault();
    if (!sessionToken) return;
    setSubmitting(true);
    setError(null);
    try {
      const payloadAnswers = task.questions_json
        .filter((q) => answers[q.id] !== undefined && answers[q.id] !== "")
        .map((q) => ({
          question_id: q.id,
          value:
            q.type === "likert" ? Number(answers[q.id]) : String(answers[q.id]),
        }));

      await apiRequest(
        "/participant/responses",
        {
          method: "POST",
          body: JSON.stringify({
            task_id: task.id,
            answers: payloadAnswers,
          }),
        },
        null,
        sessionToken
      );

      const done = await apiRequest<FlowState>(
        "/participant/complete",
        { method: "POST" },
        null,
        sessionToken
      );
      setFlow(done);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Please complete required ratings"
      );
    } finally {
      setSubmitting(false);
    }
  }

  if (error && !flow) {
    return (
      <div className="mx-auto max-w-lg rounded-xl border border-red-200 bg-red-50 p-6 text-sm text-red-800">
        {error}
      </div>
    );
  }

  if (!flow) {
    return <p className="text-sm text-slate-500">Loading study session...</p>;
  }

  const activeTask = flow.assignment?.condition.tasks[0];

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div className="flex items-center justify-between rounded-xl border border-slate-200 bg-white px-6 py-4">
        <div>
          <h1 className="text-lg font-bold text-slate-900">
            {flow.experiment_title}
          </h1>
          <p className="text-xs text-slate-500">
            Pseudonymous ID:{" "}
            <span className="font-mono font-semibold text-slate-800">
              {flow.pseudonymous_code}
            </span>
          </p>
        </div>
        <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold uppercase text-slate-700">
          Step: {flow.step}
        </span>
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {flow.step === "consent" && (
        <div className="space-y-5 rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">
          <h2 className="text-xl font-bold text-slate-900">
            Participant Information & Informed Consent
          </h2>
          <p className="whitespace-pre-line text-sm leading-relaxed text-slate-700">
            {flow.participant_information}
          </p>
          <div className="rounded-xl bg-slate-50 p-4 text-sm font-medium text-slate-800">
            {flow.consent_statement}
          </div>
          <div className="flex flex-wrap gap-3 pt-2">
            <button
              type="button"
              onClick={() => handleConsent(true)}
              className="rounded-lg bg-emerald-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-emerald-500"
            >
              I Consent & Begin Study
            </button>
            <button
              type="button"
              onClick={() => handleConsent(false)}
              className="rounded-lg border border-slate-300 bg-white px-5 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50"
            >
              I Decline
            </button>
          </div>
        </div>
      )}

      {flow.step === "declined" && (
        <div className="rounded-2xl border border-slate-200 bg-white p-8 text-center">
          <h2 className="text-xl font-bold text-slate-900">Study Declined</h2>
          <p className="mt-2 text-sm text-slate-600">
            You chose not to participate. No experimental tasks were presented.
            You may close this window.
          </p>
        </div>
      )}

      {flow.step === "assign" && (
        <div className="rounded-2xl border border-slate-200 bg-white p-8 text-center">
          <p className="text-sm text-slate-600">
            Consent recorded. Click below to initialize your assigned study
            condition.
          </p>
          <button
            type="button"
            onClick={handleAssign}
            className="mt-4 rounded-lg bg-slate-900 px-5 py-2.5 text-sm font-semibold text-white"
          >
            Continue to Task
          </button>
        </div>
      )}

      {flow.step === "tasks" && activeTask && (
        <div className="space-y-6">
          <div className="rounded-2xl border border-slate-200 bg-white p-6">
            <h2 className="text-lg font-bold text-slate-900">
              {activeTask.title}
            </h2>
            <p className="mt-1 text-sm text-slate-600">
              {activeTask.instructions}
            </p>
            {activeTask.scenario_prompt && (
              <div className="mt-4 rounded-xl border border-indigo-100 bg-indigo-50/70 p-4 text-sm text-slate-800">
                {activeTask.scenario_prompt}
              </div>
            )}
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-6">
            <h3 className="text-base font-semibold text-slate-900">
              AI Decision-Support Assistant
            </h3>
            <div className="mt-4 max-h-80 space-y-3 overflow-y-auto rounded-xl bg-slate-50 p-4">
              {flow.messages.length === 0 ? (
                <p className="text-xs text-slate-500">
                  Send a message below to consult the AI assistant on this
                  scenario.
                </p>
              ) : (
                flow.messages.map((m) => (
                  <div
                    key={m.id}
                    className={`rounded-xl px-4 py-3 text-sm ${
                      m.role === "participant"
                        ? "ml-8 bg-slate-900 text-white"
                        : "mr-8 border border-slate-200 bg-white text-slate-800"
                    }`}
                  >
                    <p className="mb-1 text-[11px] font-semibold uppercase opacity-70">
                      {m.role === "participant" ? "You" : "AI Assistant"}
                    </p>
                    <p className="whitespace-pre-line">{m.content}</p>
                  </div>
                ))
              )}
            </div>

            <form
              onSubmit={(e) => handleSendMessage(e, activeTask.id)}
              className="mt-3 flex gap-2"
            >
              <input
                type="text"
                required
                value={promptInput}
                onChange={(e) => setPromptInput(e.target.value)}
                placeholder="Ask the AI assistant for its recommendation..."
                className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm"
              />
              <button
                type="submit"
                disabled={sendingChat}
                className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-800 disabled:opacity-50"
              >
                {sendingChat ? "Sending..." : "Send"}
              </button>
            </form>
          </div>

          <form
            onSubmit={(e) => handleSubmitRatings(e, activeTask)}
            className="space-y-5 rounded-2xl border border-slate-200 bg-white p-6"
          >
            <h3 className="text-base font-semibold text-slate-900">
              Post-Task Evaluation
            </h3>
            {activeTask.questions_json.map((q) => (
              <div key={q.id} className="space-y-2">
                <label className="block text-sm font-medium text-slate-800">
                  {q.label}{" "}
                  {q.required && <span className="text-red-500">*</span>}
                </label>

                {q.type === "likert" ? (
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-xs text-slate-400">
                      Strongly Disagree ({q.min ?? 1})
                    </span>
                    {Array.from(
                      { length: (q.max ?? 7) - (q.min ?? 1) + 1 },
                      (_, i) => (q.min ?? 1) + i
                    ).map((num) => (
                      <button
                        key={num}
                        type="button"
                        onClick={() =>
                          setAnswers((prev) => ({ ...prev, [q.id]: num }))
                        }
                        className={`h-9 w-9 rounded-lg border text-sm font-semibold transition ${
                          answers[q.id] === num
                            ? "border-slate-900 bg-slate-900 text-white"
                            : "border-slate-300 bg-white text-slate-700 hover:bg-slate-50"
                        }`}
                      >
                        {num}
                      </button>
                    ))}
                    <span className="text-xs text-slate-400">
                      Strongly Agree ({q.max ?? 7})
                    </span>
                  </div>
                ) : (
                  <textarea
                    rows={2}
                    required={q.required}
                    value={String(answers[q.id] ?? "")}
                    onChange={(e) =>
                      setAnswers((prev) => ({
                        ...prev,
                        [q.id]: e.target.value,
                      }))
                    }
                    className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                  />
                )}
              </div>
            ))}

            <button
              type="submit"
              disabled={submitting}
              className="rounded-lg bg-emerald-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-emerald-500 disabled:opacity-50"
            >
              {submitting ? "Submitting..." : "Submit Responses & Complete Study"}
            </button>
          </form>
        </div>
      )}

      {flow.step === "completed" && (
        <div className="space-y-3 rounded-2xl border border-emerald-200 bg-white p-8 text-center shadow-sm">
          <span className="inline-block rounded-full bg-emerald-100 px-3 py-1 text-xs font-semibold text-emerald-800">
            Session Recorded
          </span>
          <h2 className="text-2xl font-bold text-slate-900">
            Thank You for Participating
          </h2>
          <p className="text-sm text-slate-600">
            Your interaction log and ratings have been securely recorded under
            pseudonymous ID{" "}
            <span className="font-mono font-semibold text-slate-900">
              {flow.pseudonymous_code}
            </span>
            .
          </p>
        </div>
      )}
    </div>
  );
}

export default function ParticipantStudyRunnerPage() {
  return (
    <Suspense
      fallback={<p className="text-sm text-slate-500">Loading study session...</p>}
    >
      <ParticipantStudyRunnerContent />
    </Suspense>
  );
}