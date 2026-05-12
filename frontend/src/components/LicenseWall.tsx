import { useAuth } from "../context/AuthContext";

export default function LicenseWall() {
  const { license } = useAuth();

  if (!license || license.valid) return null;

  return (
    <div className="fixed inset-0 z-50 bg-gray-900/95 flex items-center justify-center p-4">
      <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-6 text-center">
        <div className="mx-auto w-12 h-12 bg-red-100 rounded-full flex items-center justify-center mb-4">
          <svg
            className="w-6 h-6 text-red-600"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
            />
          </svg>
        </div>
        <h2 className="text-xl font-semibold text-gray-900 mb-2">
          License Expired
        </h2>
        <p className="text-gray-600 mb-4">
          Your license has expired or is invalid. Please contact support to
          renew and continue using Bundle Analyzer.
        </p>
        {license.expires_at && (
          <p className="text-sm text-gray-500 mb-4">
            Expired: {license.expires_at}
          </p>
        )}
        {license.customer_name && (
          <p className="text-sm text-gray-500 mb-4">
            Customer: {license.customer_name}
          </p>
        )}
        <p className="text-xs text-gray-400">
          License type: {license.license_type ?? "unknown"}
        </p>
      </div>
    </div>
  );
}
