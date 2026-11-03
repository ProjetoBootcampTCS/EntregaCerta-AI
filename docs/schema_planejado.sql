-- Desenho da etapa 2. Validar em memória; popular dados reais somente na etapa 3.
PRAGMA foreign_keys = ON;
CREATE TABLE customers (
  customer_id TEXT PRIMARY KEY NOT NULL,
  customer_unique_id TEXT,
  zip_prefix TEXT, city TEXT, state TEXT
);
CREATE TABLE sellers (
  seller_id TEXT PRIMARY KEY NOT NULL,
  zip_prefix TEXT, city TEXT, state TEXT
);
CREATE TABLE products (
  product_id TEXT PRIMARY KEY NOT NULL,
  category TEXT,
  weight_g REAL CHECK (weight_g IS NULL OR weight_g > 0),
  length_cm REAL CHECK (length_cm IS NULL OR length_cm > 0),
  height_cm REAL CHECK (height_cm IS NULL OR height_cm > 0),
  width_cm REAL CHECK (width_cm IS NULL OR width_cm > 0)
);
CREATE TABLE orders (
  order_id TEXT PRIMARY KEY NOT NULL,
  customer_id TEXT NOT NULL REFERENCES customers(customer_id),
  purchase_at TEXT, approved_at TEXT, estimated_delivery_day TEXT
);
CREATE TABLE order_items (
  order_id TEXT NOT NULL REFERENCES orders(order_id),
  item_id INTEGER NOT NULL CHECK(item_id > 0),
  product_id TEXT NOT NULL REFERENCES products(product_id),
  seller_id TEXT NOT NULL REFERENCES sellers(seller_id),
  price REAL CHECK(price IS NULL OR price >= 0),
  freight_value REAL CHECK(freight_value IS NULL OR freight_value >= 0),
  shipping_limit_date TEXT,
  PRIMARY KEY(order_id, item_id)
);
CREATE TABLE order_outcomes (
  order_id TEXT PRIMARY KEY NOT NULL REFERENCES orders(order_id),
  final_status TEXT, delivered_at TEXT, carrier_handoff_at TEXT,
  is_late INTEGER CHECK(is_late IN (0, 1) OR is_late IS NULL),
  label_observed_at TEXT,
  eligible INTEGER NOT NULL CHECK(eligible IN (0, 1)),
  exclusion_reasons_json TEXT NOT NULL CHECK(json_valid(exclusion_reasons_json))
);
CREATE TABLE order_features (
  order_id TEXT PRIMARY KEY NOT NULL REFERENCES orders(order_id),
  feature_version TEXT NOT NULL,
  as_of TEXT NOT NULL,
  attributes_json TEXT NOT NULL CHECK(json_valid(attributes_json)),
  quality_flags_json TEXT NOT NULL CHECK(json_valid(quality_flags_json))
);
CREATE TABLE model_versions (
  version TEXT PRIMARY KEY NOT NULL,
  artifact_sha256 TEXT NOT NULL CHECK(length(artifact_sha256) = 64),
  feature_version TEXT NOT NULL,
  protocol_id TEXT NOT NULL,
  calibration_status TEXT NOT NULL CHECK(calibration_status IN ('not_evaluated','unsupported','supported')),
  metrics_path TEXT NOT NULL
);
CREATE TABLE predictions (
  id TEXT PRIMARY KEY NOT NULL,
  order_id TEXT NOT NULL REFERENCES orders(order_id),
  model_version TEXT NOT NULL REFERENCES model_versions(version),
  score REAL NOT NULL CHECK(score >= 0 AND score <= 1),
  score_kind TEXT NOT NULL CHECK(score_kind IN ('score','probability')),
  policy_json TEXT NOT NULL CHECK(json_valid(policy_json)),
  feature_snapshot_json TEXT NOT NULL CHECK(json_valid(feature_snapshot_json)),
  created_at TEXT NOT NULL
);
CREATE TABLE reviews (
  id TEXT PRIMARY KEY NOT NULL,
  prediction_id TEXT NOT NULL REFERENCES predictions(id),
  decision TEXT NOT NULL CHECK(decision IN ('accompany','monitor','insufficient_data')),
  notes TEXT NOT NULL DEFAULT '' CHECK(length(notes) <= 2000),
  reviewed_at TEXT NOT NULL
);
CREATE TABLE reports (
  id TEXT PRIMARY KEY NOT NULL,
  prediction_id TEXT NOT NULL REFERENCES predictions(id),
  review_id TEXT REFERENCES reviews(id),
  mode TEXT NOT NULL CHECK(mode IN ('llm','factual_fallback')),
  evidence_json TEXT NOT NULL CHECK(json_valid(evidence_json)),
  content TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE INDEX idx_orders_approved ON orders(approved_at);
CREATE INDEX idx_items_seller ON order_items(seller_id);
CREATE INDEX idx_predictions_order ON predictions(order_id);
CREATE INDEX idx_reviews_prediction ON reviews(prediction_id);
