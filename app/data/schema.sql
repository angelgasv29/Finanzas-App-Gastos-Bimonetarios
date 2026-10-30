-- =============================================================================
-- Esquema SQLite — reemplaza los 5 almacenes de IndexedDB de la versión de referencia
-- =============================================================================
-- Origen: objectStoreNames y createIndex() de openDB() (líneas 2774-2811 de
-- la referencia).
--
-- Equivalencias:
--   IndexedDB object store          -> tabla
--   IndexedDB index (simple)        -> índice
--   IndexedDB index (compuesto)     -> índice de varias columnas
--   keyPath 'id' autoIncrement      -> INTEGER PRIMARY KEY AUTOINCREMENT
--
-- Los campos que en la versión de referencia son objetos o arrays (enabledFields,
-- customFields, customValues, topCategories, topExpenses) se guardan como
-- texto JSON: su forma es libre y así esta implementación mantiene exactamente las mismas
-- claves que el JavaScript.
-- =============================================================================

PRAGMA foreign_keys = ON;

-- -----------------------------------------------------------------------------
-- categories
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS categories (
    id            TEXT    PRIMARY KEY,
    workspace     TEXT    NOT NULL,
    name          TEXT    NOT NULL,
    color         TEXT    NOT NULL DEFAULT '#2563EB',
    enabledFields TEXT    NOT NULL DEFAULT '{}',  -- JSON
    customFields  TEXT    NOT NULL DEFAULT '[]',  -- JSON
    createdAt     INTEGER NOT NULL DEFAULT 0,     -- ms desde epoch
    updatedAt     INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_categories_workspace ON categories(workspace);

-- -----------------------------------------------------------------------------
-- products  (catálogo maestro de SKU; clave = el propio SKU)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS products (
    id          TEXT    PRIMARY KEY,
    workspace   TEXT    NOT NULL,
    name        TEXT    NOT NULL,
    name_lower  TEXT    NOT NULL DEFAULT '',
    categoryId  TEXT,
    brand       TEXT    NOT NULL DEFAULT '',
    unit        TEXT    NOT NULL DEFAULT '',
    subcategory TEXT    NOT NULL DEFAULT '',
    provider    TEXT    NOT NULL DEFAULT '',
    createdAt   INTEGER NOT NULL DEFAULT 0,
    updatedAt   INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_products_workspace   ON products(workspace);
CREATE INDEX IF NOT EXISTS idx_products_name_lower  ON products(name_lower);
CREATE INDEX IF NOT EXISTS idx_products_category    ON products(categoryId);

-- -----------------------------------------------------------------------------
-- transactions  (libro mayor)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS transactions (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace      TEXT    NOT NULL,
    year           INTEGER NOT NULL,           -- año fiscal derivado de date
    date           TEXT    NOT NULL,           -- YYYY-MM-DD
    productId      TEXT,
    productName    TEXT    NOT NULL DEFAULT '',
    categoryId     TEXT,
    quantity       REAL,                       -- NULL si no se indicó
    unit           TEXT    NOT NULL DEFAULT '',
    brand          TEXT    NOT NULL DEFAULT '',
    subcategory    TEXT    NOT NULL DEFAULT '',
    provider       TEXT    NOT NULL DEFAULT '',
    paymentMethod  TEXT    NOT NULL DEFAULT '',
    originPlatform TEXT    NOT NULL DEFAULT '',
    nature         TEXT    NOT NULL DEFAULT '',
    taxMode        TEXT    NOT NULL DEFAULT '',   -- exento | incluido | mas_iva
    ivaRate        REAL    NOT NULL DEFAULT 0.16, -- fracción: 0.16 = 16 %
    baseImponible  REAL    NOT NULL DEFAULT 0,
    ivaMonto       REAL    NOT NULL DEFAULT 0,
    amountBs       REAL    NOT NULL DEFAULT 0,    -- total
    amountUsd      REAL    NOT NULL DEFAULT 0,    -- total / tasa
    rate           REAL,                          -- tasa aplicada
    rateDate       TEXT,
    rateSource     TEXT    NOT NULL DEFAULT '',
    customValues   TEXT    NOT NULL DEFAULT '{}', -- JSON
    notes          TEXT    NOT NULL DEFAULT '',
    createdAt      INTEGER NOT NULL DEFAULT 0,
    updatedAt      INTEGER NOT NULL DEFAULT 0
);

-- Índices del original: workspace, date, [workspace,date], productId, year,
-- [workspace,year].
CREATE INDEX IF NOT EXISTS idx_tx_workspace       ON transactions(workspace);
CREATE INDEX IF NOT EXISTS idx_tx_date            ON transactions(date);
CREATE INDEX IF NOT EXISTS idx_tx_workspace_date  ON transactions(workspace, date);
CREATE INDEX IF NOT EXISTS idx_tx_product         ON transactions(productId);
CREATE INDEX IF NOT EXISTS idx_tx_year            ON transactions(year);
CREATE INDEX IF NOT EXISTS idx_tx_workspace_year  ON transactions(workspace, year);

-- -----------------------------------------------------------------------------
-- rates  (histórico de tasa Bs/USD; clave = la fecha)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS rates (
    date   TEXT    PRIMARY KEY,   -- YYYY-MM-DD
    value  REAL    NOT NULL,
    source TEXT    NOT NULL DEFAULT 'manual',
    ts     INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_rates_date ON rates(date);

-- -----------------------------------------------------------------------------
-- closures  (cierres anuales inmutables)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS closures (
    id            TEXT    PRIMARY KEY,
    workspace     TEXT    NOT NULL,
    year          INTEGER NOT NULL,
    closedAt      INTEGER NOT NULL DEFAULT 0,
    totalBs       REAL    NOT NULL DEFAULT 0,
    totalUsd      REAL    NOT NULL DEFAULT 0,
    ivaTotal      REAL    NOT NULL DEFAULT 0,
    baseTotal     REAL    NOT NULL DEFAULT 0,
    txCount       INTEGER NOT NULL DEFAULT 0,
    topCategories TEXT    NOT NULL DEFAULT '[]',  -- JSON
    topExpenses   TEXT    NOT NULL DEFAULT '[]',  -- JSON
    rateStart     REAL,
    rateEnd       REAL,
    rateStartDate TEXT,
    rateEndDate   TEXT,
    rateDelta     REAL    NOT NULL DEFAULT 0,
    inflationAvg  REAL    NOT NULL DEFAULT 0,
    notes         TEXT    NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_closures_workspace_year ON closures(workspace, year);

-- -----------------------------------------------------------------------------
-- config  (reemplaza las claves gb_* de localStorage, líneas 2657-2662)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS config (
    key   TEXT PRIMARY KEY,
    value TEXT
);
