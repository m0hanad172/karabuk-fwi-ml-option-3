const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function fetchApi<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json();
}

// --- Types ---

export interface LiveWeather {
  source: string;
  source_time: string | null;
  fetch_time: string;
  display_timezone: string;
  temperature_now: number | null;
  rh_now: number | null;
  ws_now: number | null;
  precip_now: number | null;
  cloud_cover_now: number | null;
  is_display_only: boolean;
}

export interface PredictionResult {
  run_id: string;
  run_type: string;
  run_timestamp: string;
  target_date: string;
  predicted_fwi: number;
  high_risk_probability: number;
  high_risk_flag: number;
  decision_reason: string;
  thresholds: {
    high_threshold: number;
    near_threshold: number;
    probability_threshold: number;
  };
  drone_state?: DroneState;
  validation?: {
    is_valid: boolean;
    missing_features: string[];
    nan_features: string[];
    checked?: number;
  };
  raw_inputs?: Record<string, unknown>;
  feature_values?: Record<string, number | null>;
}

export interface RunHistoryEntry {
  // Lean row — the DB layer drops the heavy JSON payload columns for the
  // list endpoint. Use getRunDetail() to hydrate the full audit package.
  run_id: string;
  run_type: string;
  run_timestamp: string;
  target_date: string;
  predicted_fwi: number | null;
  high_risk_probability: number | null;
  high_risk_flag: number | null;
  decision_reason: string | null;
  drone_triggered: number | null;
}

export interface RunDetail extends RunHistoryEntry {
  // Hydrated full audit package — raw API inputs, engineered features,
  // validation summary, and the thresholds the run was scored against.
  raw_inputs?: Record<string, unknown>;
  feature_values?: Record<string, number | null>;
  validation?: {
    is_valid?: boolean;
    missing_features?: string[];
    nan_features?: string[];
    checked?: number;
  };
  thresholds?: {
    high_threshold?: number;
    near_threshold?: number;
    probability_threshold?: number;
  };
}

export interface DroneState {
  active_alert_window: boolean;
  drone_status: string;
  drone_interval_minutes: number | null;
  next_launch_time: string | null;
  reason: string;
}

export interface ModelInfo {
  stage1_model: string;
  stage2_model: string;
  n_training_features: number;
  stage2_input_features: string[];
  thresholds: {
    high_threshold: number;
    near_threshold: number;
    probability_threshold: number;
  };
  stage1_test_metrics: Record<string, number> | null;
  stage2_test_metrics: Record<string, number> | null;
}

export interface HealthStatus {
  status: string;
  stage1_model_loaded: boolean;
  stage2_model_loaded: boolean;
  database_ok: boolean;
  timestamp: string;
}

export interface SchedulerStatus {
  running: boolean;
  jobs: { id: string; name: string; next_run_time: string | null }[];
}

// --- Monitoring / detection layer types ---
// These are strictly separate from the Stacked v3 prediction path above.
// Monitoring data never modifies predicted_fwi or high_risk_flag.

export interface CameraError {
  code: string;
  message: string;
}

export interface CameraStatus {
  cam_id: string;
  exists: boolean;
  running?: boolean;
  index?: number;
  detection_count?: number;
  last_error?: CameraError | null;
  capture_fps?: number;
  inference_fps?: number;
  frames_captured?: number;
  frames_inferred?: number;
  inference_stride?: number;
}

export interface CameraDevice {
  index: number;
  opened: boolean;
  width: number;
  height: number;
  fps: number;
  assigned_to: string | null;
}

export interface CameraDevicesResponse {
  devices: CameraDevice[];
  inference_stride: number;
  capture_fps_cap: number;
}

export interface AutoDetectResult {
  changed: boolean;
  reason?: string;
  previous?: Record<string, number>;
  assignments?: Record<string, number>;
  brio_detected?: boolean;
  devices: CameraDevice[];
}

export interface DroneMonitoringStatus {
  running: boolean;
  connected: boolean;
  battery: number | null;
  last_error: string | null;
  detection_count: number;
  hardware_available: boolean;
  capture_fps?: number;
  inference_fps?: number;
  inference_stride?: number;
}

export interface MonitoringNotification {
  id: string;
  source: string;
  timestamp: number;
  time_str: string;
  detection_count: number;
  max_confidence: number;
  image: string | null;
}

// --- Detection Alerts (durable evidence log) ------------------------------
// These power the Detection Alerts tab. The shape is a superset of
// MonitoringNotification — same fields plus the full per-detection list
// with bounding boxes, which the evidence log preserves.

export interface DetectionBBox {
  label: string;
  confidence: number;
  bbox: number[]; // [x1, y1, x2, y2] — may be empty if the detector didn't emit one
}

export interface DetectionAlert extends MonitoringNotification {
  detections: DetectionBBox[];
}

export interface DetectionAlertsSummary {
  total: number;
  by_source: Record<string, number>;
  max_confidence: number | null;
  last_time_str: string | null;
  last_source: string | null;
  last_by_source: Record<string, string>;
}

export interface AnalyticsData {
  dataset_range: { start: string; end: string };
  total_records: number;
  total_high_risk_days: number;
  monthly_series: { date: string; mean_fwi: number; max_fwi: number }[];
  yearly_stats: { year: number; mean_fwi: number; max_fwi: number; high_risk_days: number; total_days: number }[];
  seasonal_profile: { month: number; month_name: string; mean_fwi: number; max_fwi: number; high_risk_days: number; total_days: number }[];
  year_over_year: { year: number; month: number; month_name: string; mean_fwi: number; high_risk_days: number }[];
}

// --- API calls ---

export const api = {
  getLiveWeather: () => fetchApi<LiveWeather>("/weather/live"),
  getLatestPrediction: () => fetchApi<PredictionResult>("/risk/latest"),
  runManualCheck: (targetDate?: string, allowDrone = false) =>
    fetchApi<PredictionResult>("/risk/check", {
      method: "POST",
      body: JSON.stringify({ target_date: targetDate || null, allow_drone_trigger: allowDrone }),
    }),
  getRunHistory: (limit = 50, offset = 0) =>
    fetchApi<RunHistoryEntry[]>(`/history/runs?limit=${limit}&offset=${offset}`),
  getRunDetail: (runId: string) => fetchApi<RunDetail>(`/history/runs/${runId}`),
  getModelInfo: () => fetchApi<ModelInfo>("/system/model"),
  getHealth: () => fetchApi<HealthStatus>("/system/health"),
  getScheduler: () => fetchApi<SchedulerStatus>("/system/scheduler"),
  getDroneState: () => fetchApi<DroneState>("/drone/state"),
  getAnalytics: () => fetchApi<AnalyticsData>("/history/analytics"),

  // --- Monitoring / detection (separate from prediction path) ---
  listCameras: () => fetchApi<{ cameras: CameraStatus[] }>("/monitoring/cameras"),
  getCameraStatus: (camId: string) =>
    fetchApi<CameraStatus>(`/monitoring/cameras/${camId}/status`),
  startCamera: (camId: string) =>
    fetchApi<CameraStatus>(`/monitoring/cameras/${camId}/start`, { method: "POST" }),
  stopCamera: (camId: string) =>
    fetchApi<CameraStatus>(`/monitoring/cameras/${camId}/stop`, { method: "POST" }),
  discoverDevices: () =>
    fetchApi<CameraDevicesResponse>("/monitoring/cameras/devices"),
  remapCamera: (camId: string, newIndex: number) =>
    fetchApi<CameraStatus>(`/monitoring/cameras/${camId}/remap?new_index=${newIndex}`, {
      method: "POST",
    }),
  autoDetectCameras: () =>
    fetchApi<AutoDetectResult>("/monitoring/cameras/auto-detect", {
      method: "POST",
    }),
  getDroneMonitoringStatus: () =>
    fetchApi<DroneMonitoringStatus>("/monitoring/drone/status"),
  startDroneMonitoring: () =>
    fetchApi<DroneMonitoringStatus>("/monitoring/drone/start", { method: "POST" }),
  stopDroneMonitoring: () =>
    fetchApi<DroneMonitoringStatus>("/monitoring/drone/stop", { method: "POST" }),
  getMonitoringNotifications: (limit = 50) =>
    fetchApi<{ notifications: MonitoringNotification[] }>(
      `/monitoring/notifications?limit=${limit}`,
    ),

  // --- Detection Alerts (durable evidence log) ---------------------------
  listDetectionAlerts: (
    limit = 100,
    offset = 0,
    source?: string,
  ) => {
    const params = new URLSearchParams({
      limit: String(limit),
      offset: String(offset),
    });
    if (source) params.set("source", source);
    return fetchApi<{ alerts: DetectionAlert[] }>(
      `/monitoring/alerts?${params.toString()}`,
    );
  },
  getDetectionAlertsSummary: () =>
    fetchApi<DetectionAlertsSummary>("/monitoring/alerts/summary"),
  getDetectionAlert: (alertId: string) =>
    fetchApi<DetectionAlert>(`/monitoring/alerts/${alertId}`),
  // Cheap poll target for the in-app banner. Returns { alert: null } when
  // no alerts have been raised yet, so callers should null-check.
  getLatestDetectionAlert: () =>
    fetchApi<{ alert: DetectionAlert | null }>(
      "/monitoring/alerts/latest",
    ),
  // Demo / smoke-test endpoint — appends a synthetic alert through the
  // real persistence path. Useful when no camera/drone hardware is
  // available; alerts tagged source="demo" are easy to filter or
  // remove from the JSONL file later.
  createTestDetectionAlert: (
    label: "fire" | "smoke" = "fire",
    confidence = 0.78,
    source = "demo",
  ) => {
    const params = new URLSearchParams({
      label,
      confidence: String(confidence),
      source,
    });
    return fetchApi<DetectionAlert>(
      `/monitoring/alerts/test?${params.toString()}`,
      { method: "POST" },
    );
  },
};

// Build an absolute URL to a backend resource (MJPEG feed, static image, etc).
export function apiUrl(path: string): string {
  return `${API_BASE}${path}`;
}
