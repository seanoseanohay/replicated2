import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

type Tab = "signin" | "register";

export default function LoginPage() {
  const { login, register } = useAuth();
  const navigate = useNavigate();

  const [tab, setTab] = useState<Tab>("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      if (tab === "signin") {
        await login(email, password);
      } else {
        await register(email, password, fullName || undefined);
      }
      navigate("/");
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : "An unexpected error occurred";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-gray-900 flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        {/* Logo / title */}
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-indigo-400 tracking-tight">
            Bundle Analyzer
          </h1>
          <p className="mt-2 text-sm text-gray-400">
            Kubernetes support bundle analysis
          </p>
        </div>

        {/* Card */}
        <div className="bg-gray-800 rounded-xl shadow-xl border border-gray-700 p-8">
          {/* Tabs */}
          <div className="flex border-b border-gray-700 mb-6">
            <button
              onClick={() => { setTab("signin"); setError(null); }}
              className={`flex-1 pb-3 text-sm font-medium transition-colors ${
                tab === "signin"
                  ? "border-b-2 border-indigo-500 text-indigo-400"
                  : "text-gray-400 hover:text-gray-200"
              }`}
            >
              Sign In
            </button>
            <button
              onClick={() => { setTab("register"); setError(null); }}
              className={`flex-1 pb-3 text-sm font-medium transition-colors ${
                tab === "register"
                  ? "border-b-2 border-indigo-500 text-indigo-400"
                  : "text-gray-400 hover:text-gray-200"
              }`}
            >
              Create Account
            </button>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            {tab === "register" && (
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">
                  Full Name <span className="text-gray-500">(optional)</span>
                </label>
                <input
                  type="text"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="Jane Smith"
                  className="w-full rounded-lg bg-gray-700 border border-gray-600 text-gray-100 placeholder-gray-500 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                />
              </div>
            )}

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1">
                Email
              </label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                className="w-full rounded-lg bg-gray-700 border border-gray-600 text-gray-100 placeholder-gray-500 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1">
                Password
              </label>
              <input
                type="password"
                required
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder={tab === "register" ? "Min. 8 characters" : "••••••••"}
                className="w-full rounded-lg bg-gray-700 border border-gray-600 text-gray-100 placeholder-gray-500 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
              />
            </div>

            {error && (
              <div className="rounded-lg bg-red-900/40 border border-red-700 p-3 text-sm text-red-300">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 px-4 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-sm transition-colors disabled:opacity-50 disabled:cursor-not-allowed mt-2"
            >
              {loading
                ? tab === "signin"
                  ? "Signing in..."
                  : "Creating account..."
                : tab === "signin"
                ? "Sign In"
                : "Create Account"}
            </button>
          </form>
        </div>

        <p className="mt-6 text-center text-xs text-gray-600">
          Bundle Analyzer v0.1.0
        </p>
      </div>
    </div>
  );
}
