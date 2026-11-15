import Link from "next/link";

export default function HomePage() {
  return (
    <div className="space-y-10 py-6">
      <section className="rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">
        <p className="text-xs font-semibold uppercase tracking-wider text-indigo-600">
          Reproducible Behavioral Research Platform
        </p>
        <h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl">
          Human–AI Interaction Lab (HAI-Lab)
        </h1>
        <p className="mt-4 max-w-2xl text-base leading-relaxed text-slate-600">
          Design controlled between-subjects AI experiments, lock immutable
          study versions at publication, collect informed consent and
          pseudonymous interaction transcripts, and export analysis-ready CSV
          datasets.
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <Link
            href="/login"
            className="rounded-lg bg-slate-900 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-slate-800"
          >
            Researcher Sign In
          </Link>
          <Link
            href="/study"
            className="rounded-lg border border-slate-300 bg-white px-5 py-2.5 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
          >
            Enter Study with Invitation Token
          </Link>
        </div>
      </section>

      <section className="grid gap-6 md:grid-cols-3">
        <div className="rounded-xl border border-slate-200 bg-white p-6">
          <h2 className="text-base font-semibold text-slate-900">
            1. Immutable Study Versioning
          </h2>
          <p className="mt-2 text-sm leading-relaxed text-slate-600">
            Configure multi-arm AI conditions and post-task Likert scales, then
            freeze version snapshots on publish so participant data stays tied
            to exact study parameters.
          </p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-6">
          <h2 className="text-base font-semibold text-slate-900">
            2. Consent Gate & Persistent Assignment
          </h2>
          <p className="mt-2 text-sm leading-relaxed text-slate-600">
            Participants review study disclosures before condition assignment.
            Cryptographically uniform assignments persist across refreshes
            without re-randomization.
          </p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-6">
          <h2 className="text-base font-semibold text-slate-900">
            3. Descriptive Metrics & Safe Exports
          </h2>
          <p className="mt-2 text-sm leading-relaxed text-slate-600">
            Monitor recruitment funnels, condition balance, rating distributions
            (mean, median, SD), quality diagnostics, and formula-escaped CSV
            exports.
          </p>
        </div>
      </section>
    </div>
  );
}