"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export default function ParticipantEntryPage() {
  const router = useRouter();
  const [token, setToken] = useState("");

  function handleEnter(e: React.FormEvent) {
    e.preventDefault();
    const cleaned = token.trim().split("/").pop() || "";
    if (cleaned) {
      router.push(`/study/${encodeURIComponent(cleaned)}`);
    }
  }

  return (
    <div className="mx-auto max-w-md rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">
      <h1 className="text-xl font-bold text-slate-900">
        Participant Study Portal
      </h1>
      <p className="mt-2 text-sm text-slate-600">
        Paste your invitation token or full study link below to review study
        information and begin.
      </p>

      <form onSubmit={handleEnter} className="mt-5 space-y-4">
        <div>
          <label className="block text-sm font-medium text-slate-700">
            Invitation Token or URL
          </label>
          <input
            type="text"
            required
            value={token}
            onChange={(e) => setToken(e.target.value)}
            placeholder="Paste invitation token..."
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-slate-900 focus:outline-none"
          />
        </div>
        <button
          type="submit"
          className="w-full rounded-lg bg-slate-900 py-2.5 text-sm font-semibold text-white hover:bg-slate-800"
        >
          Continue to Study Information
        </button>
      </form>
    </div>
  );
}