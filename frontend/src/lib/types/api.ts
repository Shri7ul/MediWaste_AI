export interface PolicyMetadata {
    policy_version: string;
    facility_profile: string;
    accept_threshold: number;
    review_floor: number;
    valid_routes: string[];
    route_meta: Record<string, RouteMeta>;
}

export interface RouteMeta {
    code?: string;
    hex: string;
    label: string;
    category?: string;
    description?: string;
    bin_asset?: string | null;
    selectable?: boolean;
}

export interface HealthStatus {
    status: string;
    policy_version: string;
    config: {
        roboflow_configured: boolean;
        pinecone_configured: boolean;
        openrouter_configured: boolean;
        model_ref: string;
        pinecone_index: string;
        openrouter_model: string;
        cors_enabled: boolean;
    };
    features: {
        disposal_workflow_steps: number;
        operations_bins: string;
    };
    audit_events: number;
}

export interface AnalyzeResponse {
    status: string;
    event_id: string;
    image_url: string;
    analysis: {
        detections: any[];
        primary: {
            item: string;
            confidence: number;
        };
        decision: {
            waste_type: string;
            expected_route: string;
            rule_id: string;
            policy_version: string;
        };
        context: any;
        mixed_waste: boolean;
        verification: ComplianceVerification;
        model: {
            id: string;
            version: string;
            ref: string;
        };
        valid_routes: string[];
        route_meta: Record<string, RouteMeta>;
    };
    rag: RagResult;
    explanation: Explanation;
    audit_event: any;
    timings: any;
}

export interface ComplianceVerification {
    status: 'CORRECT' | 'VIOLATION' | 'REVIEW_REQUIRED' | 'PENDING';
    reason_code?: string;
}

export interface VerifyResponse {
    status: string;
    event_id: string;
    verification: ComplianceVerification;
    rag: RagResult;
    explanation: Explanation;
    audit_event: any;
}

/**
 * One retrieved passage from Pinecone (rag_engine._normalise_hit).
 * The backend text field is `text` (NOT `content`); id field is `evidence_id`.
 * source/page/section/score may be null and must be rendered defensively.
 */
export interface EvidenceRecord {
    evidence_id: string | null;
    score: number | null;
    text: string | null;
    source: string | null;
    page: string | number | null;
    section: string | null;
    metadata?: Record<string, any>;
    relevance?: 'RELEVANT' | 'UNCERTAIN' | 'IRRELEVANT';
    relevance_score?: number | null;
}

/**
 * rag_engine.retrieve_evidence() return. status is "OK" on success —
 * NOT "SUCCESS". Emptiness is driven ONLY by `evidence.length`.
 */
export interface RagResult {
    status: 'OK' | 'INSUFFICIENT_EVIDENCE' | 'NO_RESULTS' | 'UNAVAILABLE';
    query?: string;
    namespace?: string;
    text_field?: string | null;
    evidence: EvidenceRecord[];
    evidence_all?: EvidenceRecord[];
    evidence_ids: string[];
    retrieved_count?: number;
    retained_count?: number;
    latency_ms?: number;
    error?: string | null;
}

/**
 * llm_client.generate_explanation() return. status is "OK" on success —
 * NOT "SUCCESS". "SKIPPED_NO_EVIDENCE" = grounding gate withheld the narrative;
 * "UNAVAILABLE" = model/key unavailable. The route decision stands regardless.
 */
export interface Explanation {
    status: 'OK' | 'SKIPPED_NO_EVIDENCE' | 'UNAVAILABLE';
    explanation: string | null;
    why_route: string | null;
    guidance: string[];
    evidence_ids_used: string[];
    limitations: string | null;
    model?: string;
    latency_ms?: number;
}

export interface ActiveJobSummary {
    job_id: string;
    status: 'IN_PROGRESS' | 'COMPLETED';
    item_count: number;
    completed_count: number;
    total_steps: number;
    current_step: string | null;
    current_step_label: string | null;
}

export interface BinOperation {
    bin_id: string;
    route_code: string;
    label: string;
    category?: string;
    hex?: string;
    description?: string;
    capacity_units: number;
    fill_percent: number;
    fill_status: 'OK' | 'MODERATE' | 'HIGH' | 'CRITICAL';
    routed_event_count: number;
    pending_collection_count: number;
    active_job?: ActiveJobSummary | null;
    data_source: string;
    sensing: string;
}

export interface OperationsOverview {
    data_source: string;
    disclaimer: string;
    total_bins: number;
    bins_needing_attention: number;
    attention: string[];
    collections?: {
        total: number;
        in_progress: number;
        completed: number;
    };
    bins: BinOperation[];
}

export interface WorkflowDefinition {
    total_steps: number;
    steps: Array<{
        id: string;
        name: string;
        description: string;
    }>;
}

export interface WorkflowStepState {
    id: string;
    order: number;
    label: string;
    description: string;
    status: 'PENDING' | 'DONE';
    completed_at: string | null;
}
export interface DisposalWorkflow {
    event_id: string;
    steps: WorkflowStepState[];
    current_step: string | null;
    completed_count: number;
    total_steps: number;
    is_complete: boolean;
    note: string;
}

/**
 * A BIN COLLECTION JOB — one operational disposal/collection cycle for a bin /
 * waste stream. It references a SNAPSHOT of existing audit event_ids; it never
 * owns, mutates, or deletes those events. Distinct domain object from an event.
 */
export interface CollectionJobWorkflow {
    steps: WorkflowStepState[];
    current_step: string | null;
    completed_count: number;
    total_steps: number;
    is_complete: boolean;
    workflow_source?: string;
    workflow_version?: string;
    note: string;
}

export interface CollectionJob {
    job_id: string;
    bin_id: string;
    route_code: string;
    waste_stream?: string | null;
    route_meta?: RouteMeta;
    ward?: string | null;
    status: 'IN_PROGRESS' | 'COMPLETED';
    event_ids: string[];
    event_count: number;
    created_at: string;
    updated_at?: string | null;
    completed_at?: string | null;
    workflow: CollectionJobWorkflow;
}

/**
 * Per-category / per-ward / per-station compliance bucket
 * (audit_store.analytics `_bucket`). Every count is a REAL event tally.
 */
export interface AnalyticsBucket {
    total: number;
    correct: number;
    violations: number;
    review_required: number;
    pending: number;
}

export interface TopViolation {
    event_id: string;
    waste_type: string;
    expected_route: string | null;
    actual_route: string | null;
    reason_code: string | null;
    station: string | null;
    ward: string | null;
    created_at: string | null;
}

/**
 * audit_store.analytics() return. Everything is computed live from persisted
 * events; the frontend must NOT recalculate these figures. Rates are `null`
 * (not 0) when there is no denominator, so "0%" is distinguishable from
 * "not enough data yet".
 */
export interface AnalyticsData {
    total_events: number;
    correct: number;
    violations: number;
    review_required: number;
    pending_verification: number;
    verified: number;
    compliance_rate: number | null;
    violation_rate: number | null;
    review_rate: number | null;
    by_waste_type: Record<string, AnalyticsBucket>;
    by_station: Record<string, AnalyticsBucket>;
    by_ward: Record<string, AnalyticsBucket>;
    top_violations: TopViolation[];
    has_station_data: boolean;
    has_ward_data: boolean;
    violations_by_waste_type: Record<string, number>;
    violations_by_route: Record<string, number>;
    station_performance: Record<string, AnalyticsBucket>;
    data_source: string;
}

/** Compliance status persisted on an audit event. */
export type ComplianceStatus =
    | 'CORRECT'
    | 'VIOLATION'
    | 'REVIEW_REQUIRED'
    | 'PENDING_VERIFICATION';

/**
 * A single audit event row (audit_store._row_to_dict). JSON columns
 * (detected_items, raw_labels, visual_context, evidence_ids, payload) are
 * decoded server-side. The list endpoint and detail endpoint return the same
 * shape; detail additionally carries a fully-populated `payload`.
 */
export interface EventRecord {
    event_id: string;
    created_at: string | null;
    updated_at?: string | null;
    image_filename?: string | null;
    image_id?: string | null;
    station?: string | null;
    ward?: string | null;
    detected_items?: string[] | null;
    raw_labels?: string[] | null;
    confidence?: number | null;
    visual_context?: any;
    canonical_category: string | null;
    expected_route: string | null;
    actual_route: string | null;
    compliance_status: ComplianceStatus | null;
    reason_code?: string | null;
    rule_id?: string | null;
    policy_version?: string | null;
    model_id?: string | null;
    model_version?: string | null;
    evidence_ids?: string[] | null;
    rag_status?: RagResult['status'] | null;
    llm_status?: Explanation['status'] | null;
    collection_job_id?: string | null;
    payload?: EventPayload | null;
}

/** payload JSON blob persisted alongside an event (app.py). */
export interface EventPayload {
    decision?: Record<string, any>;
    primary?: Record<string, any>;
    detections?: any[];
    mixed_waste?: boolean;
    context?: any;
    rag?: RagResult;
    explanation?: Explanation;
    verification?: ComplianceVerification;
    [key: string]: any;
}
