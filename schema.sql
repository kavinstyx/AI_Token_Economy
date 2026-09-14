-- schema.sql — auto-run by MySQL on first container start

CREATE TABLE IF NOT EXISTS model_specs (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    model_name      VARCHAR(100) NOT NULL UNIQUE,   -- must match litellm model_name
    is_local        BOOLEAN NOT NULL DEFAULT FALSE,
    cost_hint       VARCHAR(100),                   -- human-readable cost note
    strengths       TEXT,                           -- what it's good at
    weaknesses      TEXT,                           -- what it's weak at
    active          BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS routing_rules (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    priority        INT NOT NULL,                   -- lower = checked first
    condition_type  VARCHAR(40) NOT NULL,           -- 'keyword' | 'max_chars' | 'default'
    condition_value VARCHAR(255),                   -- e.g. "python,sql,legal" or "240"
    target_model    VARCHAR(100) NOT NULL,          -- model_name to use if matched
    reason_label    VARCHAR(255),                   -- shown in the UI
    active          BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS usage_raw (
    id                INT AUTO_INCREMENT PRIMARY KEY,
    ts                DATETIME NOT NULL,
    user_key          VARCHAR(100),
    mode              VARCHAR(40),
    requested_model   VARCHAR(100),
    served_model      VARCHAR(100),
    decider_rule      VARCHAR(100),
    prompt_tokens     INT,
    completion_tokens INT,
    total_tokens      INT,
    prompt_chars      INT,
    routing_source    VARCHAR(20)                   -- 'db' | 'fallback' | 'manual'
);

-- seed model specs
INSERT INTO model_specs (model_name, is_local, cost_hint, strengths, weaknesses) VALUES
('local-qwen',   TRUE,  'very low (our own machine)', 'cheap, private, fine for simple prompts', 'slow on CPU, weaker on hard tasks'),
('gemini-flash', FALSE, 'per-token (external API)',   'strong, fast, good for hard/long tasks',  'costs money, external, trains on free-tier data');

-- seed routing rules (first match by priority wins)
INSERT INTO routing_rules (priority, condition_type, condition_value, target_model, reason_label) VALUES
(1,  'keyword',   'code,python,javascript,sql,regex,algorithm,legal,contract,medical,translate,prove,analyze,essay', 'gemini-flash', 'Detected a harder/specialist task'),
(2,  'max_chars', '240', 'gemini-flash', 'Long prompt — needs a stronger model'),
(99, 'default',   NULL,  'local-qwen',   'Short, simple prompt — local model can handle it (low-cost path)');