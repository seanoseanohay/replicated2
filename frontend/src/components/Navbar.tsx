import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";


const ROLE_BADGE: Record<string, string> = {
  analyst: "bg-blue-900/50 text-blue-300 border border-blue-700",
  manager: "bg-purple-900/50 text-purple-300 border border-purple-700",
  admin: "bg-red-900/50 text-red-300 border border-red-700",
};

const ROLE_LABEL: Record<string, string> = {
  analyst: "Analyst",
  manager: "Manager",
  admin: "Admin",
};

export default function Navbar() {
  const { user, logout, isManager } = useAuth();

  if (!user) return null;

  return (
    <header className="bg-gray-900 border-b border-gray-700 shadow-sm">
      <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-6">
          <Link
            to="/"
            className="text-xl font-bold text-indigo-400 tracking-tight hover:text-indigo-300 transition-colors"
          >
            Bundle Analyzer
          </Link>
          <Link
            to="/dashboard"
            className="text-sm text-gray-300 hover:text-white transition-colors"
          >
            Dashboard
          </Link>
          <Link
            to="/bundles"
            className="text-sm text-gray-300 hover:text-white transition-colors"
          >
            Bundles
          </Link>
          <Link
            to="/bundles/compare"
            className="text-sm text-gray-300 hover:text-white transition-colors"
          >
            Compare
          </Link>
          {isManager && (
            <Link
              to="/settings/notifications"
              className="text-sm text-gray-300 hover:text-white transition-colors"
            >
              Settings
            </Link>
          )}
        </div>

        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-400 hidden sm:inline">
              {user.email}
            </span>
            <span
              className={`px-2 py-0.5 rounded text-xs font-medium ${
                ROLE_BADGE[user.role] ?? "bg-gray-700 text-gray-300"
              }`}
            >
              {ROLE_LABEL[user.role] ?? user.role}
            </span>
          </div>

          <button
            onClick={logout}
            className="text-sm text-gray-400 hover:text-gray-200 transition-colors px-2 py-1 rounded hover:bg-gray-800"
          >
            Logout
          </button>
        </div>
      </div>
    </header>
  );
}
