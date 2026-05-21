-- ════════════════════════════════════════════════════════
-- HELMET DETECTION SYSTEM — DATABASE SCHEMA
-- SQLite (used by Flask-SQLAlchemy in app.py)
-- ════════════════════════════════════════════════════════

-- Users Table
CREATE TABLE IF NOT EXISTS user (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            VARCHAR(100) NOT NULL,
    email           VARCHAR(120) UNIQUE NOT NULL,
    password_hash   VARCHAR(256) NOT NULL,
    vehicle_number  VARCHAR(20),
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Challans Table
CREATE TABLE IF NOT EXISTS challan (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    challan_number  VARCHAR(20) UNIQUE NOT NULL,
    vehicle_number  VARCHAR(20) NOT NULL,
    violation       VARCHAR(200) DEFAULT 'Not wearing helmet',
    location        VARCHAR(200),
    fine_amount     REAL DEFAULT 500.0,
    status          VARCHAR(20) DEFAULT 'Unpaid',   -- Unpaid | Paid
    detected_image  TEXT,                            -- base64 JPEG
    detected_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
    camera_id       VARCHAR(50),
    confidence      REAL
);

-- ════════════════════════════════════════════════════════
-- DEMO SEED DATA
-- Run via: POST http://localhost:5000/api/seed
-- ════════════════════════════════════════════════════════

-- Demo users (passwords hashed by app – these are raw for reference)
-- rider@demo.com / demo123   — has challans for MH12AB1234
-- admin@demo.com / demo123   — admin / traffic officer

INSERT OR IGNORE INTO user (name, email, password_hash, vehicle_number) VALUES
    ('Ravi Kumar',     'rider@demo.com', '<hashed_by_app>', 'MH12AB1234'),
    ('Admin Officer',  'admin@demo.com', '<hashed_by_app>', NULL);

-- Sample challans
INSERT OR IGNORE INTO challan 
    (challan_number, vehicle_number, violation, location, fine_amount, status, camera_id, confidence, detected_at)
VALUES
    ('CH20241201001', 'MH12AB1234', 'Not wearing helmet while riding', 'FC Road, Pune',          500, 'Unpaid', 'CAM-001', 0.94, datetime('now', '-1 hour')),
    ('CH20241130002', 'MH12AB1234', 'Not wearing helmet while riding', 'MG Road, Bangalore',      500, 'Paid',   'CAM-003', 0.88, datetime('now', '-1 day')),
    ('CH20241129003', 'MH12AB1234', 'Not wearing helmet while riding', 'Bandra, Mumbai',          500, 'Unpaid', 'CAM-007', 0.96, datetime('now', '-2 days')),
    ('CH20241201004', 'KA03CD5678', 'Not wearing helmet while riding', 'Whitefield, Bangalore',   500, 'Unpaid', 'CAM-002', 0.91, datetime('now', '-3 hours')),
    ('CH20241201005', 'DL09EF9012', 'Not wearing helmet while riding', 'Connaught Place, Delhi',  500, 'Unpaid', 'CAM-005', 0.87, datetime('now', '-5 hours')),
    ('CH20241130006', 'TN07GH3456', 'Not wearing helmet while riding', 'Anna Salai, Chennai',     500, 'Paid',   'CAM-009', 0.93, datetime('now', '-36 hours'));

-- ════════════════════════════════════════════════════════
-- USEFUL QUERIES
-- ════════════════════════════════════════════════════════

-- All unpaid challans
-- SELECT * FROM challan WHERE status = 'Unpaid' ORDER BY detected_at DESC;

-- Challans for a specific vehicle
-- SELECT * FROM challan WHERE vehicle_number = 'MH12AB1234' ORDER BY detected_at DESC;

-- Total fines collected
-- SELECT SUM(fine_amount) as total_collected FROM challan WHERE status = 'Paid';

-- Pending fines
-- SELECT SUM(fine_amount) as pending FROM challan WHERE status = 'Unpaid';

-- Detection stats by camera
-- SELECT camera_id, COUNT(*) as detections, AVG(confidence) as avg_conf FROM challan GROUP BY camera_id;

-- Top offenders
-- SELECT vehicle_number, COUNT(*) as violations FROM challan WHERE status='Unpaid' GROUP BY vehicle_number ORDER BY violations DESC;
