import { Link, Outlet, useLocation } from "react-router-dom";

export default function Layout() {
  const { pathname } = useLocation();

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <header className="bg-white border-b border-gray-200 shadow-sm">
        <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between">
          <Link to="/" className="text-xl font-bold text-indigo-600 tracking-tight">
            Bundle Analyzer
          </Link>
          <nav className="flex gap-4 text-sm font-medium">
            <Link
              to="/"
              className={`hover:text-indigo-600 transition-colors ${
                pathname === "/" ? "text-indigo-600" : "text-gray-600"
              }`}
            >
              Bundles
            </Link>
            <Link
              to="/upload"
              className={`hover:text-indigo-600 transition-colors ${
                pathname === "/upload" ? "text-indigo-600" : "text-gray-600"
              }`}
            >
              Upload
            </Link>
          </nav>
        </div>
      </header>

      <main className="flex-1 max-w-6xl w-full mx-auto px-4 py-8">
        <Outlet />
      </main>

      <footer className="border-t border-gray-200 text-center text-xs text-gray-400 py-4">
        Bundle Analyzer v0.1.0
      </footer>
    </div>
  );
}
