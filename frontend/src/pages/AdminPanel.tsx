import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { adminApi, type AdminUser, type AdminStats } from "../api/client";

const ROLES = ["analyst", "manager", "admin"] as const;

const ROLE_BADGE: Record<string, string> = {
  analyst: "bg-blue-100 text-blue-700 border border-blue-200",
  manager: "bg-purple-100 text-purple-700 border border-purple-200",
  admin: "bg-red-100 text-red-700 border border-red-200",
};

function StatCard({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-5 shadow-sm">
      <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">{label}</p>
      <p className="text-3xl font-bold text-gray-900">{value}</p>
    </div>
  );
}

export default function AdminPanel() {
  const { user, isAdmin } = useAuth();

  const [users, setUsers] = useState<AdminUser[] | null>(null);
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [updatingId, setUpdatingId] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([adminApi.listUsers(), adminApi.getStats()])
      .then(([u, s]) => {
        setUsers(u);
        setStats(s);
      })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, []);

  if (!isAdmin) return <Navigate to="/dashboard" replace />;

  const handleRoleChange = async (userId: string, role: string) => {
    setUpdatingId(userId);
    try {
      const updated = await adminApi.updateRole(userId, role);
      setUsers((prev) => prev?.map((u) => (u.id === userId ? updated : u)) ?? prev);
    } catch (e) {
      alert(`Failed to update role: ${e}`);
    } finally {
      setUpdatingId(null);
    }
  };

  const handleStatusToggle = async (u: AdminUser) => {
    if (u.id === user?.id) return; // can't deactivate yourself
    setUpdatingId(u.id);
    try {
      const updated = await adminApi.updateStatus(u.id, !u.is_active);
      setUsers((prev) => prev?.map((x) => (x.id === u.id ? updated : x)) ?? prev);
    } catch (e) {
      alert(`Failed to update status: ${e}`);
    } finally {
      setUpdatingId(null);
    }
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Admin Panel</h1>
        <p className="text-sm text-gray-500 mt-1">Manage users and view system stats</p>
      </div>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <StatCard label="Total Users" value={stats.total_users} />
          <StatCard label="Total Bundles" value={stats.total_bundles} />
          <StatCard label="Total Findings" value={stats.total_findings} />
          <StatCard
            label="Roles"
            value={Object.entries(stats.users_by_role)
              .map(([r, n]) => `${n} ${r}`)
              .join(" · ")}
          />
        </div>
      )}

      {/* Users table */}
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-100">
          <h2 className="text-sm font-semibold text-gray-700">Users</h2>
        </div>

        {loading && (
          <div className="p-8 text-center text-sm text-gray-400">Loading…</div>
        )}
        {error && (
          <div className="p-8 text-center text-sm text-red-500">{error}</div>
        )}
        {users && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-xs text-gray-500 uppercase tracking-wider">
                <tr>
                  <th className="px-4 py-3 text-left">Email</th>
                  <th className="px-4 py-3 text-left">Name</th>
                  <th className="px-4 py-3 text-left">Tenant</th>
                  <th className="px-4 py-3 text-left">Role</th>
                  <th className="px-4 py-3 text-left">Status</th>
                  <th className="px-4 py-3 text-left">Joined</th>
                  <th className="px-4 py-3 text-left">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {users.map((u) => {
                  const isSelf = u.id === user?.id;
                  const busy = updatingId === u.id;
                  return (
                    <tr key={u.id} className={`hover:bg-gray-50 transition-colors ${!u.is_active ? "opacity-50" : ""}`}>
                      <td className="px-4 py-3 font-medium text-gray-900">
                        {u.email}
                        {isSelf && (
                          <span className="ml-2 text-xs text-gray-400">(you)</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-gray-600">{u.full_name ?? "—"}</td>
                      <td className="px-4 py-3 text-gray-500 font-mono text-xs">{u.tenant_id}</td>
                      <td className="px-4 py-3">
                        <span className={`px-2 py-0.5 rounded text-xs font-medium ${ROLE_BADGE[u.role] ?? "bg-gray-100 text-gray-600"}`}>
                          {u.role}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <span className={`inline-flex items-center gap-1 text-xs font-medium ${u.is_active ? "text-green-600" : "text-gray-400"}`}>
                          <span className={`w-1.5 h-1.5 rounded-full ${u.is_active ? "bg-green-500" : "bg-gray-300"}`} />
                          {u.is_active ? "Active" : "Inactive"}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-gray-400 text-xs">
                        {new Date(u.created_at).toLocaleDateString()}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          {/* Role selector */}
                          <select
                            value={u.role}
                            disabled={busy}
                            onChange={(e) => handleRoleChange(u.id, e.target.value)}
                            className="text-xs border border-gray-200 rounded px-2 py-1 bg-white focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-300 disabled:opacity-50"
                          >
                            {ROLES.map((r) => (
                              <option key={r} value={r}>{r}</option>
                            ))}
                          </select>

                          {/* Activate / Deactivate */}
                          {!isSelf && (
                            <button
                              onClick={() => handleStatusToggle(u)}
                              disabled={busy}
                              className={`text-xs px-2 py-1 rounded border transition-colors disabled:opacity-50 ${
                                u.is_active
                                  ? "border-red-200 text-red-600 hover:bg-red-50"
                                  : "border-green-200 text-green-600 hover:bg-green-50"
                              }`}
                            >
                              {u.is_active ? "Deactivate" : "Activate"}
                            </button>
                          )}

                          {busy && (
                            <svg className="w-3.5 h-3.5 animate-spin text-gray-400" fill="none" viewBox="0 0 24 24">
                              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                            </svg>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
