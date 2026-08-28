import { AnalyzeResponse, VerifyResponse, HealthStatus, PolicyMetadata, OperationsOverview, WorkflowDefinition, DisposalWorkflow, AnalyticsData, EventRecord, CollectionJob, FacilityContext } from '../types/api';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:5000';

/** Resolve a backend-relative asset path (e.g. /uploads/x.jpg) to an absolute URL. */
export function apiAsset(path: string | null | undefined): string | undefined {
  if (!path) return undefined;
  if (/^https?:\/\//i.test(path)) return path;
  return `${API_BASE}${path.startsWith('/') ? '' : '/'}${path}`;
}

export class ApiError extends Error {
  public status: number;
  public code?: string;
  
  constructor(message: string, status: number, code?: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

async function fetchApi<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  
  const headers = new Headers(options.headers);
  if (!(options.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let errorMsg = 'An unexpected error occurred.';
    let errorCode: string | undefined;
    try {
      const errorData = await response.json();
      errorMsg = errorData.error || errorMsg;
      errorCode = errorData.code;
    } catch {
      if (response.status === 409) {
          errorMsg = "Complete the current step first.";
      } else if (response.status === 503) {
          errorMsg = "This service is temporarily unavailable.";
      }
    }
    throw new ApiError(errorMsg, response.status, errorCode);
  }

  return response.json();
}

// API methods
export const api = {
  analyze: (formData: FormData): Promise<AnalyzeResponse> => 
    fetchApi<AnalyzeResponse>('/analyze', { method: 'POST', body: formData }),
    
  verify: (data: { event_id: string; actual_route: string; station?: string; ward?: string }): Promise<VerifyResponse> =>
    fetchApi<VerifyResponse>('/verify', { method: 'POST', body: JSON.stringify(data) }),

  health: (): Promise<HealthStatus> => 
    fetchApi<HealthStatus>('/health'),

  policy: (): Promise<PolicyMetadata> =>
    fetchApi<PolicyMetadata>('/policy'),

  /** Configured facility wards — the single source of truth for the ward selector. */
  facilityWards: (): Promise<FacilityContext & { status: string }> =>
    fetchApi<FacilityContext & { status: string }>('/facility/wards'),

  operations: (): Promise<{ status: string; operations: OperationsOverview }> =>
    fetchApi<{ status: string; operations: OperationsOverview }>('/operations'),

  analytics: (): Promise<{ status: string; analytics: AnalyticsData }> =>
    fetchApi<{ status: string; analytics: AnalyticsData }>('/analytics'),

  events: (limit = 100, offset = 0): Promise<{ status: string; count: number; events: EventRecord[] }> =>
    fetchApi<{ status: string; count: number; events: EventRecord[] }>(`/events?limit=${limit}&offset=${offset}`),

  eventDetail: (eventId: string): Promise<{ status: string; event: EventRecord }> =>
    fetchApi<{ status: string; event: EventRecord }>(`/events/${eventId}`),

  /**
   * Workflow DEFINITION from the backend. Pass a route code to get that stream's
   * route-specific step list (step counts differ per route and are never
   * hardcoded in the frontend).
   */
  disposalDefinition: (route?: string | null): Promise<WorkflowDefinition & { status: string }> =>
    fetchApi<WorkflowDefinition & { status: string }>(
      route ? `/disposal/definition?route=${encodeURIComponent(route)}` : '/disposal/definition'
    ),

  disposalWorkflow: (eventId: string): Promise<{ status: string; workflow: DisposalWorkflow }> =>
    fetchApi<{ status: string; workflow: DisposalWorkflow }>(`/disposal/${eventId}`),

  completeDisposalStep: (eventId: string, stepId: string): Promise<any> =>
    fetchApi<any>(`/disposal/${eventId}/steps/${stepId}/complete`, { method: 'POST' }),

  // --- Bin collection jobs (operational cycles over multiple audit events) ---
  startCollectionJob: (binId: string): Promise<{ status: string; job: CollectionJob; resumed: boolean }> =>
    fetchApi<{ status: string; job: CollectionJob; resumed: boolean }>('/disposal/jobs', {
      method: 'POST',
      body: JSON.stringify({ bin_id: binId }),
    }),

  collectionJob: (jobId: string): Promise<{ status: string; job: CollectionJob }> =>
    fetchApi<{ status: string; job: CollectionJob }>(`/disposal/jobs/${jobId}`),

  completeCollectionStep: (jobId: string, stepId: string): Promise<{ status: string; job: CollectionJob }> =>
    fetchApi<{ status: string; job: CollectionJob }>(`/disposal/jobs/${jobId}/steps/${stepId}/complete`, { method: 'POST' }),

  collectionJobEvents: (jobId: string): Promise<{ status: string; job_id: string; count: number; events: EventRecord[] }> =>
    fetchApi<{ status: string; job_id: string; count: number; events: EventRecord[] }>(`/disposal/jobs/${jobId}/events`)
};
