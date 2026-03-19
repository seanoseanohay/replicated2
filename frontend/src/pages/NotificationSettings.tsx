import { useEffect, useState } from "react";
import { notificationApi, type NotificationConfig } from "../api/client";
import { useAuth } from "../context/AuthContext";

export default function NotificationSettings() {
  const { isManager } = useAuth();
  const [config, setConfig] = useState<NotificationConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [savedOk, setSavedOk] = useState(false);

  // Local form state
  const [emailEnabled, setEmailEnabled] = useState(false);
  const [emailRecipients, setEmailRecipients] = useState("");
  const [slackEnabled, setSlackEnabled] = useState(false);
  const [slackWebhookUrl, setSlackWebhookUrl] = useState("");
  const [notifyOnSeverities, setNotifyOnSeverities] = useState("critical,high");

  useEffect(() => {
    if (!isManager) {
      setLoading(false);
      return;
    }
    notificationApi
      .getConfig()
      .then((c) => {
        setConfig(c);
        setEmailEnabled(c.email_enabled);
        setEmailRecipients(c.email_recipients ?? "");
        setSlackEnabled(c.slack_enabled);
        setSlackWebhookUrl(c.slack_webhook_url ?? "");
        setNotifyOnSeverities(c.notify_on_severities);
      })
      .catch((e) => console.error("Failed to load notification config", e))
      .finally(() => setLoading(false));
  }, [isManager]);

  const handleSave = async () => {
    setSaving(true);
    setSaveError(null);
    setSavedOk(false);
    try {
      const updated = await notificationApi.updateConfig({
        email_enabled: emailEnabled,
        email_recipients: emailRecipients || null,
        slack_enabled: slackEnabled,
        slack_webhook_url: slackWebhookUrl || null,
        notify_on_severities: notifyOnSeverities,
      });
      setConfig(updated);
      setSavedOk(true);
      setTimeout(() => setSavedOk(false), 3000);
    } catch (e) {
      setSaveError(String(e));
    } finally {
      setSaving(false);
    }
  };

  if (!isManager) {
    return (
      <div className="max-w-lg mx-auto mt-16 text-center">
        <p className="text-gray-500">Manager access required to view notification settings.</p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="max-w-lg mx-auto mt-16 text-center">
        <p className="text-gray-400 text-sm">Loading...</p>
      </div>
    );
  }

  return (
    <div className="max-w-lg mx-auto">
      <h1 className="text-xl font-bold text-gray-800 mb-6">Notification Settings</h1>

      <div className="bg-white rounded-lg border border-gray-200 p-6 space-y-6 shadow-sm">
        {/* Email */}
        <section>
          <h2 className="text-sm font-semibold text-gray-700 mb-3">Email Notifications</h2>
          <label className="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={emailEnabled}
              onChange={(e) => setEmailEnabled(e.target.checked)}
              className="w-4 h-4 text-indigo-600 rounded"
            />
            <span className="text-sm text-gray-700">Enable Email Notifications</span>
          </label>
          {emailEnabled && (
            <div className="mt-3">
              <label className="block text-xs text-gray-500 mb-1">
                Email Recipients (comma-separated)
              </label>
              <input
                type="text"
                className="w-full text-sm border border-gray-200 rounded px-3 py-2 focus:outline-none focus:ring-1 focus:ring-indigo-300"
                placeholder="alice@example.com, bob@example.com"
                value={emailRecipients}
                onChange={(e) => setEmailRecipients(e.target.value)}
              />
            </div>
          )}
        </section>

        {/* Slack */}
        <section>
          <h2 className="text-sm font-semibold text-gray-700 mb-3">Slack Notifications</h2>
          <label className="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={slackEnabled}
              onChange={(e) => setSlackEnabled(e.target.checked)}
              className="w-4 h-4 text-indigo-600 rounded"
            />
            <span className="text-sm text-gray-700">Enable Slack Notifications</span>
          </label>
          {slackEnabled && (
            <div className="mt-3">
              <label className="block text-xs text-gray-500 mb-1">Slack Webhook URL</label>
              <input
                type="url"
                className="w-full text-sm border border-gray-200 rounded px-3 py-2 focus:outline-none focus:ring-1 focus:ring-indigo-300"
                placeholder="https://hooks.slack.com/services/..."
                value={slackWebhookUrl}
                onChange={(e) => setSlackWebhookUrl(e.target.value)}
              />
            </div>
          )}
        </section>

        {/* Severities */}
        <section>
          <h2 className="text-sm font-semibold text-gray-700 mb-3">Alert Severities</h2>
          <label className="block text-xs text-gray-500 mb-1">
            Notify on Severities (comma-separated)
          </label>
          <input
            type="text"
            className="w-full text-sm border border-gray-200 rounded px-3 py-2 focus:outline-none focus:ring-1 focus:ring-indigo-300"
            placeholder="critical,high"
            value={notifyOnSeverities}
            onChange={(e) => setNotifyOnSeverities(e.target.value)}
          />
          <p className="mt-1 text-xs text-gray-400">
            Allowed values: critical, high, medium, low, info
          </p>
        </section>

        {/* Save */}
        <div className="flex items-center gap-4">
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-4 py-2 text-sm rounded bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-50"
          >
            {saving ? "Saving..." : "Save Settings"}
          </button>
          {savedOk && (
            <span className="text-sm text-green-600">Settings saved.</span>
          )}
          {saveError && (
            <span className="text-sm text-red-600">{saveError}</span>
          )}
        </div>
      </div>

      {config && (
        <p className="mt-4 text-xs text-gray-400">
          Last updated: {new Date(config.updated_at).toLocaleString()}
        </p>
      )}
    </div>
  );
}
