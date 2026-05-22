CREATE TABLE IF NOT EXISTS leads (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    linkedin_url        TEXT UNIQUE NOT NULL,
    brand               TEXT NOT NULL DEFAULT 'default',
    first_name          TEXT NOT NULL,
    last_name           TEXT,
    full_name           TEXT,
    title               TEXT,
    company_name        TEXT,
    industry            TEXT,
    location            TEXT,
    headline            TEXT,
    about_snippet       TEXT,
    recent_post_1       TEXT,
    recent_post_2       TEXT,
    recent_post_3       TEXT,
    connection_degree   TEXT,
    status              TEXT NOT NULL DEFAULT 'not_contacted',
    source_list         TEXT,
    imported_at         DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_activity_at    DATETIME,
    notes               TEXT,
    calendly_booked     INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS outreach_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id         INTEGER NOT NULL REFERENCES leads(id),
    brand           TEXT NOT NULL DEFAULT 'default',
    stage           TEXT NOT NULL,
    message_text    TEXT NOT NULL,
    sent_at         DATETIME DEFAULT CURRENT_TIMESTAMP,
    status          TEXT NOT NULL DEFAULT 'sent',
    error_message   TEXT
);

CREATE TABLE IF NOT EXISTS daily_stats (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    date                    TEXT NOT NULL,
    brand                   TEXT NOT NULL DEFAULT 'default',
    connections_sent        INTEGER DEFAULT 0,
    messages_sent           INTEGER DEFAULT 0,
    replies_received        INTEGER DEFAULT 0,
    bookings_detected       INTEGER DEFAULT 0,
    session_duration_mins   INTEGER DEFAULT 0,
    errors_encountered      INTEGER DEFAULT 0,
    inmails_sent            INTEGER DEFAULT 0,
    created_at              DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(date, brand)
);

CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status);
CREATE INDEX IF NOT EXISTS idx_leads_brand ON leads(brand);
CREATE INDEX IF NOT EXISTS idx_leads_last_activity ON leads(last_activity_at);
CREATE INDEX IF NOT EXISTS idx_outreach_log_lead_id ON outreach_log(lead_id);
CREATE INDEX IF NOT EXISTS idx_outreach_log_sent_at ON outreach_log(sent_at);
CREATE INDEX IF NOT EXISTS idx_daily_stats_date ON daily_stats(date);
