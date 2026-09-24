-- CTTX National Infrastructure Index
-- Schema version 1.0  2026-09-24
-- Separated: public commercial info | engineering data | PII (minimal, POPIA)

PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

-- ─── CORE PROPERTY REGISTRY ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS properties (
    property_id         TEXT PRIMARY KEY,          -- cttx-PROVINCE-YYYYMMDD-NNNN
    name                TEXT NOT NULL,
    property_type       TEXT NOT NULL,             -- game_reserve|farm|wind_project|solar_project|mine|lodge|campus|hospital|municipal|other
    province            TEXT,
    municipality        TEXT,
    latitude            REAL,
    longitude           REAL,
    area_ha             REAL,
    source              TEXT NOT NULL,             -- osm|dffe|cadastral|manual|tender
    source_reference    TEXT,
    discovery_date      TEXT NOT NULL,
    enrichment_status   TEXT DEFAULT 'RAW',        -- RAW|ENRICHED|VERIFIED|STALE
    infrastructure_status TEXT DEFAULT 'UNKNOWN',  -- UNKNOWN|CANDIDATE|ASSESSED|DEPLOYED
    assessment_status   TEXT DEFAULT 'NONE',       -- NONE|DESK_STUDY|SITE_SURVEY|COMPLETE
    opportunity_profile TEXT DEFAULT 'UNKNOWN',    -- LOW|MODERATE|HIGH|UNKNOWN
    opportunity_evidence TEXT,
    confidence          TEXT DEFAULT 'LOW',        -- LOW|MEDIUM|HIGH|VERIFIED
    last_verified       TEXT,
    notes               TEXT,
    created_at          TEXT DEFAULT (datetime('now')),
    updated_at          TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_properties_province ON properties(province);
CREATE INDEX IF NOT EXISTS idx_properties_type ON properties(property_type);
CREATE INDEX IF NOT EXISTS idx_properties_status ON properties(enrichment_status);
CREATE INDEX IF NOT EXISTS idx_properties_opportunity ON properties(opportunity_profile);

-- ─── PUBLIC COMMERCIAL CONTACTS (POPIA: public business info only) ────────────
CREATE TABLE IF NOT EXISTS commercial_contacts (
    contact_id          TEXT PRIMARY KEY,
    property_id         TEXT NOT NULL REFERENCES properties(property_id),
    organisation        TEXT,
    public_contact_name TEXT,
    public_contact_role TEXT,
    public_contact_email TEXT,   -- public business email only
    public_contact_phone TEXT,   -- public business number only
    website             TEXT,
    linkedin_company    TEXT,
    source              TEXT NOT NULL,             -- website|company_register|tender_doc|osm|manual
    source_url          TEXT,
    source_date         TEXT,
    popia_basis         TEXT DEFAULT 'public_business_contact',
    created_at          TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_contacts_property ON commercial_contacts(property_id);

-- ─── ENGINEERING OBSERVATIONS ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS engineering_observations (
    obs_id              TEXT PRIMARY KEY,
    property_id         TEXT NOT NULL REFERENCES properties(property_id),
    obs_type            TEXT NOT NULL,             -- terrain|los|mast|power|fibre|radio|antenna|building|road
    obs_key             TEXT NOT NULL,
    obs_value           TEXT,
    unit                TEXT,
    source              TEXT NOT NULL,             -- srtm|osm|survey|link_planner|manual
    verified_by         TEXT,
    verified_date       TEXT,
    confidence          TEXT DEFAULT 'LOW',        -- LOW|MEDIUM|HIGH|VERIFIED
    evidence_ref        TEXT,
    notes               TEXT,
    created_at          TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_obs_property ON engineering_observations(property_id);
CREATE INDEX IF NOT EXISTS idx_obs_type ON engineering_observations(obs_type);

-- ─── INFRASTRUCTURE SITES (masts, high points, backbone nodes) ────────────────
CREATE TABLE IF NOT EXISTS infrastructure_sites (
    site_id             TEXT PRIMARY KEY,
    property_id         TEXT NOT NULL REFERENCES properties(property_id),
    site_name           TEXT,
    site_type           TEXT NOT NULL,             -- candidate_high|existing_mast|building_roof|water_tower|known_carrier|backbone_node
    latitude            REAL NOT NULL,
    longitude           REAL NOT NULL,
    elevation_m         REAL,
    mast_height_m       REAL,
    classification      TEXT DEFAULT 'Mapped',     -- Mapped|Observed|Corroborated|Engineering_candidate|Verified
    source              TEXT NOT NULL,
    verified_by         TEXT,
    verified_date       TEXT,
    confidence          TEXT DEFAULT 'LOW',
    notes               TEXT,
    created_at          TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_sites_property ON infrastructure_sites(property_id);
CREATE INDEX IF NOT EXISTS idx_sites_type ON infrastructure_sites(site_type);

-- ─── LOS LINKS ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS los_links (
    link_id             TEXT PRIMARY KEY,
    property_id         TEXT REFERENCES properties(property_id),
    site_a_id           TEXT REFERENCES infrastructure_sites(site_id),
    site_b_id           TEXT REFERENCES infrastructure_sites(site_id),
    distance_km         REAL,
    bearing_deg         REAL,
    clearance_f1_m      REAL,       -- Fresnel zone 1 clearance
    los_status          TEXT,       -- CLEAR|MARGINAL|OBSTRUCTED|UNKNOWN
    frequency_ghz       REAL,
    path_loss_db        REAL,
    calculation_source  TEXT,       -- srtm_local|link_planner|survey
    confidence          TEXT DEFAULT 'LOW',
    notes               TEXT,
    created_at          TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_los_property ON los_links(property_id);

-- ─── ASSESSMENTS ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS assessments (
    assessment_id       TEXT PRIMARY KEY,
    property_id         TEXT NOT NULL REFERENCES properties(property_id),
    assessment_type     TEXT NOT NULL,             -- DESK_STUDY|SITE_SURVEY
    status              TEXT DEFAULT 'PENDING',    -- PENDING|IN_PROGRESS|COMPLETE|CANCELLED
    assigned_to         TEXT,
    scheduled_date      TEXT,
    completed_date      TEXT,
    price_ex_vat        REAL,
    report_path         TEXT,
    snapshot_path       TEXT,
    kmz_path            TEXT,
    processing_time_s   REAL,
    notes               TEXT,
    created_at          TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_assessments_property ON assessments(property_id);
CREATE INDEX IF NOT EXISTS idx_assessments_status ON assessments(status);

-- ─── OUTPUT ARTIFACTS ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS artifacts (
    artifact_id         TEXT PRIMARY KEY,
    property_id         TEXT REFERENCES properties(property_id),
    assessment_id       TEXT REFERENCES assessments(assessment_id),
    artifact_type       TEXT NOT NULL,             -- SNAPSHOT_PDF|KMZ|FIELD_CHECKLIST|REPORT|PROPOSAL|DRAFT_EMAIL
    file_path           TEXT,
    generated_at        TEXT DEFAULT (datetime('now')),
    generated_by        TEXT DEFAULT 'cttx-engine',
    version             INTEGER DEFAULT 1,
    status              TEXT DEFAULT 'CURRENT'     -- CURRENT|SUPERSEDED|DRAFT
);

-- ─── TENDER REGISTER ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tenders (
    tender_id           TEXT PRIMARY KEY,
    reference           TEXT,
    issuing_org         TEXT,
    description         TEXT,
    category            TEXT,                      -- telecoms|fibre|wireless|managed_services|other
    published_date      TEXT,
    closing_date        TEXT,
    submission_date     TEXT,
    status              TEXT DEFAULT 'DISCOVERED',  -- DISCOVERED|SUBMITTED|AUDITED|WON|LOST|WITHDRAWN
    cttx_submission_path TEXT,
    source_path         TEXT,
    audit_status        TEXT DEFAULT 'PENDING',
    notes               TEXT,
    created_at          TEXT DEFAULT (datetime('now'))
);

-- ─── TENDER AUDIT CRITERIA ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tender_audit (
    audit_id            TEXT PRIMARY KEY,
    tender_id           TEXT NOT NULL REFERENCES tenders(tender_id),
    criterion           TEXT NOT NULL,
    available_points    REAL,
    tender_requirement  TEXT,
    cttx_response       TEXT,
    evidence_location   TEXT,
    evidence_strength   TEXT,      -- EXPLICITLY_DEMONSTRATED|SUPPORTED|PARTIALLY_SUPPORTED|NOT_EXPLICITLY_DEMONSTRATED|NOT_FOUND
    missing_information TEXT,
    compliance_status   TEXT,      -- COMPLIANT|PARTIAL|NON_COMPLIANT|UNKNOWN
    auditor_notes       TEXT,
    created_at          TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_audit_tender ON tender_audit(tender_id);

-- ─── OUTREACH DRAFTS ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS outreach_drafts (
    draft_id            TEXT PRIMARY KEY,
    property_id         TEXT REFERENCES properties(property_id),
    contact_id          TEXT REFERENCES commercial_contacts(contact_id),
    draft_type          TEXT DEFAULT 'ASSESSMENT_OFFER',
    subject             TEXT,
    body_path           TEXT,
    status              TEXT DEFAULT 'PENDING_REVIEW', -- PENDING_REVIEW|APPROVED|SENT|CANCELLED
    created_at          TEXT DEFAULT (datetime('now')),
    reviewed_at         TEXT,
    sent_at             TEXT,       -- populated only by human action
    sent_by             TEXT        -- populated only by human action
);

-- ─── SYSTEM HEALTH LOG ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS system_health (
    health_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    component           TEXT NOT NULL,
    status              TEXT NOT NULL,             -- PASS|FAIL|PARTIAL|UNKNOWN
    detail              TEXT,
    checked_at          TEXT DEFAULT (datetime('now'))
);

-- ─── AUDIT TRAIL ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS audit_trail (
    trail_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type         TEXT NOT NULL,
    entity_id           TEXT NOT NULL,
    action              TEXT NOT NULL,
    old_value           TEXT,
    new_value           TEXT,
    performed_by        TEXT DEFAULT 'cttx-engine',
    performed_at        TEXT DEFAULT (datetime('now'))
);
