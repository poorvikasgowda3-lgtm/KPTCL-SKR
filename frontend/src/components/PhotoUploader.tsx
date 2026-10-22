import { useEffect, useRef, useState } from "react";
import type { AppConfig } from "../types/report";

type Props = {
  config: AppConfig | null;
  onExtract: (file: File) => Promise<void>;
  onSample: () => void;
  busy: boolean;
};

export default function PhotoUploader({ config, onExtract, onSample, busy }: Props) {
  const cameraRef = useRef<HTMLInputElement>(null);
  const galleryRef = useRef<HTMLInputElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [cameraOpen, setCameraOpen] = useState(false);

  useEffect(() => {
    if (cameraOpen && videoRef.current && streamRef.current) {
      videoRef.current.srcObject = streamRef.current;
      void videoRef.current.play().catch(() => {
        setError("Camera preview could not start. Use the phone camera picker instead.");
      });
    }
    return () => {
      streamRef.current?.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    };
  }, [cameraOpen]);

  function stopCamera() {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    setCameraOpen(false);
  }

  async function openCamera() {
    setError("");
    if (!navigator.mediaDevices?.getUserMedia || !window.isSecureContext) {
      cameraRef.current?.click();
      return;
    }
    try {
      streamRef.current = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { ideal: "environment" } },
        audio: false,
      });
      setCameraOpen(true);
    } catch {
      setError("Browser camera access was denied or unavailable. Use “Open phone camera” below or upload a photo.");
    }
  }

  async function capturePhoto() {
    const video = videoRef.current;
    if (!video?.videoWidth || !video.videoHeight) {
      setError("Camera is still starting. Wait a moment and try again.");
      return;
    }
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const context = canvas.getContext("2d");
    if (!context) {
      setError("Could not capture from this camera. Use the phone camera picker instead.");
      return;
    }
    context.drawImage(video, 0, 0, canvas.width, canvas.height);
    canvas.toBlob((blob) => {
      if (!blob) {
        setError("Could not create a photo from the camera.");
        return;
      }
      chooseFile(new File([blob], `notebook-${Date.now()}.jpg`, { type: "image/jpeg" }));
      stopCamera();
    }, "image/jpeg", 0.92);
  }

  function chooseFile(next: File | undefined) {
    if (!next) return;
    if (preview) URL.revokeObjectURL(preview);
    setError("");
    setSuccess("");
    setFile(next);
    setPreview(URL.createObjectURL(next));
  }

  function clearFile() {
    stopCamera();
    if (preview) URL.revokeObjectURL(preview);
    setPreview("");
    setFile(null);
    if (cameraRef.current) cameraRef.current.value = "";
    if (galleryRef.current) galleryRef.current.value = "";
    setError("");
    setSuccess("");
  }

  async function extract() {
    if (!file) return;
    setError("");
    setSuccess("");
    try {
      await onExtract(file);
      setSuccess("Photo read. Review the extracted readings below, correct anything unclear, then generate the WhatsApp report.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not extract readings.");
    }
  }

  const maxMb = Math.round((config?.max_upload_bytes ?? 10 * 1024 * 1024) / 1024 / 1024);

  return (
    <section className="card upload-card">
      <div className="section-heading">
        <div>
          <span className="eyebrow">STEP 1</span>
          <h2>Upload notebook photo</h2>
          <p>Use a clear, well-lit picture of the full notebook page.</p>
        </div>
        <span className="step-icon" aria-hidden="true">01</span>
      </div>
      {!config?.ocr_configured && (
        <div className="notice notice-info">
          <strong>Handwriting recognition is not configured.</strong>
          <span>
            Create a project-root <code>.env</code> file from <code>.env.example</code>, add your private <code>GEMINI_API_KEY</code>, and restart the backend. For the legacy Streamlit app, you can instead set the key in Streamlit secrets. Manual editing and fictional sample mode work without a key.
          </span>
        </div>
      )}
      <input
        ref={cameraRef}
        className="visually-hidden"
        type="file"
        accept="image/*"
        capture="environment"
        onChange={(event) => chooseFile(event.currentTarget.files?.[0])}
      />
      <input
        ref={galleryRef}
        className="visually-hidden"
        type="file"
        accept="image/jpeg,image/png,image/webp,image/bmp"
        onChange={(event) => chooseFile(event.currentTarget.files?.[0])}
      />
      <div className="upload-actions">
        <button className="button button-primary" onClick={() => void openCamera()} type="button">
          <span aria-hidden="true">▣</span> Take Photo
        </button>
        <button className="button button-secondary" onClick={() => galleryRef.current?.click()} type="button">
          Upload from Gallery
        </button>
      </div>
      <button className="camera-picker-link" type="button" onClick={() => cameraRef.current?.click()}>
        Open phone camera picker
      </button>
      {!window.isSecureContext && (
        <p className="helper-text">Camera preview requires HTTPS or localhost. On a phone using a local network address, use “Open phone camera” or upload a gallery photo.</p>
      )}
      {error && !cameraOpen && (
        <button className="button button-outline add-button" type="button" onClick={() => cameraRef.current?.click()}>
          Open phone camera
        </button>
      )}
      {cameraOpen && (
        <div className="camera-preview">
          <video ref={videoRef} autoPlay playsInline muted aria-label="Live notebook camera preview" />
          <div className="upload-actions">
            <button className="button button-accent" type="button" onClick={() => void capturePhoto()}>Capture Photo</button>
            <button className="button button-secondary" type="button" onClick={stopCamera}>Cancel camera</button>
          </div>
        </div>
      )}
      {preview && (
        <div className="image-preview">
          <img src={preview} alt="Notebook page selected for extraction" />
          <div className="preview-footer">
            <span className="file-name">{file?.name}</span>
            <button className="button button-quiet" type="button" onClick={clearFile}>Remove photo</button>
          </div>
        </div>
      )}
      {error && <div className="notice notice-error" role="alert">{error}</div>}
      {success && <div className="notice notice-success" role="status">{success}</div>}
      {file && (
        <button className="button button-accent extract-button" type="button" disabled={busy} onClick={() => void extract()}>
          {busy ? <><span className="spinner" /> Reading notebook…</> : "Read Photo & Extract Readings"}
        </button>
      )}
      {config?.ocr_configured && !file && <p className="helper-text">Image limit: {maxMb} MB. The photo is processed for extraction, not saved as a draft.</p>}
      <button className="sample-link" type="button" onClick={onSample}>Try fictional sample data</button>
    </section>
  );
}
