const API_BASE = import.meta.env.VITE_API_URL ?? "";

// ---- Auth types ----
export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  role: string;
  tenant_id: string;
}

export interface UserRead {
  id: string;
  email: string;
  full_name: string | null;
  role: string;
  tenant_id: string;
  is_active: boolean;
  created_at: string;
}

export interface Bundle {
  id: string;
  filename: string;
  original_filename: string;
  size_bytes: number;
  status: "uploaded" | "processing" | "ready" | "error";
  tenant_id: string;
  s3_key: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface BundleListResponse {
  items: Bundle[];
  total: number;
}

export interface Finding {
  id: string;
  bundle_id: string;
  rule_id: string;
  title: string;
  severity: "critical" | "high" | "medium" | "low" | "info";
  summary: string;
  evidence_ids: string[];
  status: "open" | "acknowledged" | "resolved";
  reviewer_notes: string | null;
  reviewed_by: string | null;
  reviewed_at: string | null;
  ai_explanation: string | null;
  ai_remediation: string | null;
  ai_explained_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface FindingListResponse {
  items: Finding[];
  total: number;
}

export interface FindingUpdate {
  status?: "open" | "acknowledged" | "resolved";
  reviewer_notes?: string;
  reviewed_by?: string;
}

export interface EvidenceRead {
  id: string;
  bundle_id: string;
  kind: string;
  name: string;
  namespace: string | null;
  source_path: string;
  raw_data: Record<string, unknown>;
  created_at: string;
}

function getAuthHeaders(): Record<string, string> {
  const token = localStorage.getItem("access_token");
  const headers: Record<string, string> = {
    "X-Tenant-ID": "default",
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  return headers;
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  tenantId = "default"
): Promise<T> {
  const url = `${API_BASE}${path}`;
  const authHeaders = getAuthHeaders();
  authHeaders["X-Tenant-ID"] = tenantId;
  const res = await fetch(url, {
    ...options,
    headers: {
      ...authHeaders,
      ...options.headers,
    },
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API error ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

async function requestText(
  path: string,
  options: RequestInit = {},
  tenantId = "default"
): Promise<string> {
  const url = `${API_BASE}${path}`;
  const authHeaders = getAuthHeaders();
  authHeaders["X-Tenant-ID"] = tenantId;
  const res = await fetch(url, {
    ...options,
    headers: {
      ...authHeaders,
      ...options.headers,
    },
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API error ${res.status}: ${text}`);
  }
  return res.text();
}

export const bundleApi = {
  list(tenantId = "default"): Promise<BundleListResponse> {
    return request<BundleListResponse>("/api/v1/bundles", {}, tenantId);
  },

  get(id: string, tenantId = "default"): Promise<Bundle> {
    return request<Bundle>(`/api/v1/bundles/${id}`, {}, tenantId);
  },

  upload(file: File, tenantId = "default"): Promise<Bundle> {
    const form = new FormData();
    form.append("file", file);
    return request<Bundle>(
      "/api/v1/bundles",
      { method: "POST", body: form },
      tenantId
    );
  },

  uploadWithProgress(
    file: File,
    tenantId = "default",
    onProgress?: (pct: number) => void
  ): Promise<Bundle> {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      const form = new FormData();
      form.append("file", file);

      xhr.open("POST", `${API_BASE}/api/v1/bundles`);
      xhr.setRequestHeader("X-Tenant-ID", tenantId);

      if (onProgress) {
        xhr.upload.addEventListener("progress", (e) => {
          if (e.lengthComputable) {
            onProgress(Math.round((e.loaded / e.total) * 100));
          }
        });
      }

      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve(JSON.parse(xhr.responseText));
        } else {
          reject(new Error(`Upload failed: ${xhr.status} ${xhr.responseText}`));
        }
      };
      xhr.onerror = () => reject(new Error("Network error during upload"));
      xhr.send(form);
    });
  },

  delete(id: string, tenantId = "default"): Promise<void> {
    return request<void>(`/api/v1/bundles/${id}`, { method: "DELETE" }, tenantId);
  },

  reanalyze(id: string, tenantId = "default"): Promise<{ bundle_id: string; status: string }> {
    return request<{ bundle_id: string; status: string }>(
      `/api/v1/bundles/${id}/reanalyze`,
      { method: "POST" },
      tenantId
    );
  },
};

export const findingApi = {
  list(
    bundleId: string,
    params?: { severity?: string; status?: string },
    tenantId = "default"
  ): Promise<FindingListResponse> {
    const qs = new URLSearchParams();
    if (params?.severity) qs.set("severity", params.severity);
    if (params?.status) qs.set("finding_status", params.status);
    const query = qs.toString() ? `?${qs.toString()}` : "";
    return request<FindingListResponse>(
      `/api/v1/bundles/${bundleId}/findings${query}`,
      {},
      tenantId
    );
  },

  update(
    bundleId: string,
    findingId: string,
    update: FindingUpdate,
    tenantId = "default"
  ): Promise<Finding> {
    return request<Finding>(
      `/api/v1/bundles/${bundleId}/findings/${findingId}`,
      {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(update),
      },
      tenantId
    );
  },

  explain(bundleId: string, findingId: string, tenantId = "default"): Promise<Finding> {
    return request<Finding>(
      `/api/v1/bundles/${bundleId}/findings/${findingId}/explain`,
      { method: "POST" },
      tenantId
    );
  },

  downloadReport(bundleId: string, tenantId = "default"): Promise<string> {
    return requestText(`/api/v1/bundles/${bundleId}/report.md`, {}, tenantId);
  },
};

export const evidenceApi = {
  getEvidence(bundleId: string, evidenceId: string, tenantId = "default"): Promise<EvidenceRead> {
    return request<EvidenceRead>(
      `/api/v1/bundles/${bundleId}/evidence/${evidenceId}`,
      {},
      tenantId
    );
  },
};

export interface BundleHealthSummary {
  bundle_id: string;
  filename: string;
  status: string;
  uploaded_at: string;
  health_score: number;
  health_color: "green" | "yellow" | "orange" | "red";
  findings_by_severity: Record<string, number>;
  open_findings: number;
  total_findings: number;
}

export interface DashboardStats {
  total_bundles: number;
  bundles_ready: number;
  bundles_processing: number;
  bundles_error: number;
  total_open_findings: number;
  findings_by_severity: Record<string, number>;
  most_recent_critical: Array<{
    bundle_id: string;
    filename: string;
    finding_title: string;
    rule_id: string;
    created_at: string;
  }>;
  bundles: BundleHealthSummary[];
}

export const dashboardApi = {
  getStats(): Promise<DashboardStats> {
    return request<DashboardStats>("/api/v1/dashboard");
  },
};

// ---- Finding Events ----
export interface FindingEvent {
  id: string;
  finding_id: string;
  actor: string;
  event_type: string;
  old_value: string | null;
  new_value: string | null;
  note: string | null;
  created_at: string;
}

export const eventsApi = {
  getEvents(bundleId: string, findingId: string, tenantId = "default"): Promise<FindingEvent[]> {
    return request<FindingEvent[]>(
      `/api/v1/bundles/${bundleId}/findings/${findingId}/events`,
      {},
      tenantId
    );
  },
};

// ---- Notifications ----
export interface NotificationConfig {
  id: string;
  tenant_id: string;
  email_enabled: boolean;
  email_recipients: string | null;
  slack_enabled: boolean;
  slack_webhook_url: string | null;
  notify_on_severities: string;
  created_at: string;
  updated_at: string;
}

export const notificationApi = {
  getConfig(): Promise<NotificationConfig> {
    return request<NotificationConfig>("/api/v1/notifications/config");
  },
  updateConfig(update: Partial<NotificationConfig>): Promise<NotificationConfig> {
    return request<NotificationConfig>("/api/v1/notifications/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(update),
    });
  },
};

// ---- Comments ----
export interface Comment {
  id: string;
  finding_id: string;
  actor: string;
  body: string;
  created_at: string;
  updated_at: string;
}

export const commentApi = {
  list(bundleId: string, findingId: string, tenantId = "default"): Promise<Comment[]> {
    return request<Comment[]>(
      `/api/v1/bundles/${bundleId}/findings/${findingId}/comments`,
      {},
      tenantId
    );
  },
  create(bundleId: string, findingId: string, body: string, tenantId = "default"): Promise<Comment> {
    return request<Comment>(
      `/api/v1/bundles/${bundleId}/findings/${findingId}/comments`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ body }),
      },
      tenantId
    );
  },
  delete(bundleId: string, findingId: string, commentId: string, tenantId = "default"): Promise<void> {
    return request<void>(
      `/api/v1/bundles/${bundleId}/findings/${findingId}/comments/${commentId}`,
      { method: "DELETE" },
      tenantId
    );
  },
};

// ---- AI Chat ----
export interface ChatMessage {
  id: string;
  finding_id: string;
  role: "user" | "assistant";
  content: string;
  actor: string;
  created_at: string;
}

export const chatApi = {
  list(bundleId: string, findingId: string, tenantId = "default"): Promise<ChatMessage[]> {
    return request<ChatMessage[]>(
      `/api/v1/bundles/${bundleId}/findings/${findingId}/chat`,
      {},
      tenantId
    );
  },
  send(bundleId: string, findingId: string, message: string, tenantId = "default"): Promise<ChatMessage> {
    return request<ChatMessage>(
      `/api/v1/bundles/${bundleId}/findings/${findingId}/chat`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message }),
      },
      tenantId
    );
  },
};

// ---- Bundle Comparison ----
export interface FindingSummary {
  rule_id: string;
  title: string;
  severity: string;
  status: string;
}

export interface ComparisonResult {
  bundle_a_id: string;
  bundle_a_filename: string;
  bundle_b_id: string;
  bundle_b_filename: string;
  new_findings: FindingSummary[];
  resolved_findings: FindingSummary[];
  persisting_findings: FindingSummary[];
  summary: { new: number; resolved: number; persisting: number };
}

export const comparisonApi = {
  compare(bundleAId: string, bundleBId: string, tenantId = "default"): Promise<ComparisonResult> {
    return request<ComparisonResult>(
      `/api/v1/bundles/compare?bundle_a=${bundleAId}&bundle_b=${bundleBId}`,
      {},
      tenantId
    );
  },
};

export const authApi = {
  login(email: string, password: string): Promise<TokenResponse> {
    return request<TokenResponse>("/api/v1/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
  },

  register(email: string, password: string, fullName?: string): Promise<TokenResponse> {
    return request<TokenResponse>("/api/v1/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password, full_name: fullName ?? null }),
    });
  },

  refresh(refreshToken: string): Promise<TokenResponse> {
    return request<TokenResponse>("/api/v1/auth/refresh", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
  },

  me(): Promise<UserRead> {
    return request<UserRead>("/api/v1/auth/me");
  },
};

// ---- Admin ----
export interface AdminUser {
  id: string;
  email: string;
  full_name: string | null;
  role: string;
  tenant_id: string;
  is_active: boolean;
  created_at: string;
}

export interface AdminStats {
  total_users: number;
  total_bundles: number;
  total_findings: number;
  users_by_role: Record<string, number>;
}

export const adminApi = {
  listUsers(): Promise<AdminUser[]> {
    return request<AdminUser[]>("/api/v1/admin/users");
  },
  updateRole(userId: string, role: string): Promise<AdminUser> {
    return request<AdminUser>(`/api/v1/admin/users/${userId}/role`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ role }),
    });
  },
  updateStatus(userId: string, is_active: boolean): Promise<AdminUser> {
    return request<AdminUser>(`/api/v1/admin/users/${userId}/status`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ is_active }),
    });
  },
  getStats(): Promise<AdminStats> {
    return request<AdminStats>("/api/v1/admin/stats");
  },
};
