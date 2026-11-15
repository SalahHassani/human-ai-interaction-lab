const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export function getResearcherToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("hai_researcher_token");
}

export function setResearcherToken(token: string | null): void {
  if (typeof window === "undefined") return;
  if (token) {
    localStorage.setItem("hai_researcher_token", token);
  } else {
    localStorage.removeItem("hai_researcher_token");
  }
}

export async function apiRequest<T>(
  path: string,
  options: RequestInit = {},
  token?: string | null,
  participantToken?: string | null
): Promise<T> {
  const headers = new Headers(options.headers || {});
  if (!headers.has("Content-Type") && options.body) {
    headers.set("Content-Type", "application/json");
  }
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  if (participantToken) {
    headers.set("X-Participant-Token", participantToken);
  }

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
    cache: "no-store",
  });

  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const err = await res.json();
      if (err?.detail) {
        detail =
          typeof err.detail === "string"
            ? err.detail
            : JSON.stringify(err.detail);
      }
    } catch {
      // ignore non-JSON body
    }
    throw new Error(detail);
  }

  return res.json() as Promise<T>;
}

export async function downloadExperimentCsv(
  experimentId: string,
  dataset: string,
  token: string
): Promise<void> {
  const res = await fetch(
    `${API_BASE}/experiments/${experimentId}/export?dataset=${encodeURIComponent(dataset)}`,
    {
      headers: { Authorization: `Bearer ${token}` },
    }
  );
  if (!res.ok) {
    throw new Error(`Export failed (${res.status})`);
  }
  const blob = await res.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `hai_lab_${dataset}.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
}