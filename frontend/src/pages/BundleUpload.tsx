import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { bundleApi } from "../api/client";

type UploadState = "idle" | "uploading" | "success" | "error";

export default function BundleUpload() {
  const [state, setState] = useState<UploadState>("idle");
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const fileRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();

  async function handleUpload(file: File) {
    setState("uploading");
    setError(null);
    setUploadProgress(0);
    try {
      const bundle = await bundleApi.uploadWithProgress(file, "default", (pct) => {
        setUploadProgress(pct);
      });
      setState("success");
      setTimeout(() => navigate(`/bundles/${bundle.id}`), 800);
    } catch (e: unknown) {
      setState("error");
      setError(String(e));
    }
  }

  function onFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) handleUpload(file);
  }

  function onDrop(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) handleUpload(file);
  }

  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Upload Support Bundle</h1>

      <div
        className={`rounded-xl border-2 border-dashed p-12 text-center transition-colors cursor-pointer ${
          dragging
            ? "border-indigo-400 bg-indigo-50"
            : "border-gray-300 hover:border-indigo-300 hover:bg-gray-50"
        }`}
        onClick={() => fileRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
      >
        <input
          ref={fileRef}
          type="file"
          accept=".tar.gz,.tgz,.tar,.zip,.gz"
          className="hidden"
          onChange={onFileChange}
          disabled={state === "uploading"}
        />

        {state === "idle" && (
          <>
            <svg
              className="mx-auto mb-4 h-12 w-12 text-gray-300"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"
              />
            </svg>
            <p className="text-gray-600 font-medium">
              Drag and drop a support bundle here, or click to browse
            </p>
            <p className="mt-1 text-sm text-gray-400">
              Supported formats: .tar.gz, .tgz, .tar, .zip, .gz (max 500 MB)
            </p>
          </>
        )}

        {state === "uploading" && (
          <div className="flex flex-col items-center gap-3">
            <div className="h-10 w-10 rounded-full border-4 border-indigo-200 border-t-indigo-600 animate-spin" />
            <p className="text-gray-600">Uploading...</p>
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div
                className="bg-blue-600 h-2 rounded-full transition-all"
                style={{ width: `${uploadProgress}%` }}
              />
            </div>
            <p className="text-sm text-gray-500">{uploadProgress}%</p>
          </div>
        )}

        {state === "success" && (
          <div className="flex flex-col items-center gap-2 text-green-600">
            <svg className="h-12 w-12" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
            <p className="font-medium">Upload successful! Redirecting...</p>
          </div>
        )}

        {state === "error" && (
          <div className="flex flex-col items-center gap-2 text-red-600">
            <svg className="h-12 w-12" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
            <p className="font-medium">Upload failed</p>
            {error && <p className="text-sm">{error}</p>}
            <button
              className="mt-2 text-sm underline hover:no-underline"
              onClick={(e) => {
                e.stopPropagation();
                setState("idle");
                setError(null);
              }}
            >
              Try again
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
