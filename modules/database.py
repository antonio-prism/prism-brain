"""
PRISM Brain - Database Module
=============================
Handles all data persistence using SQLite.
"""

import sqlite3
import json
import os
from datetime import datetime
from pathlib import Path

# Get the data directory path
DATA_DIR = Path(__file__).parent.parent / "data"
DB_PATH = DATA_DIR / "prism_brain.db"


def get_connection():
    """Get a database connection."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row  # Enable column access by name
    return conn


def init_database():
    """Initialize the database with required tables."""
    conn = get_connection()
    cursor = conn.cursor()

    # Clients table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            location TEXT,
            industry TEXT,
            revenue REAL,
            employees INTEGER,
            currency TEXT DEFAULT 'EUR',
            export_percentage REAL DEFAULT 0,
            primary_markets TEXT,
            sectors TEXT,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Client processes table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS client_processes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL,
            process_id TEXT NOT NULL,
            process_name TEXT NOT NULL,
            custom_name TEXT,
            category TEXT,
            criticality_per_day REAL DEFAULT 0,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE
        )
    ''')

    # Prioritized risks table (risks selected for a client)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS client_risks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL,
            risk_id TEXT NOT NULL,
            risk_name TEXT NOT NULL,
            domain TEXT,
            category TEXT,
            probability REAL DEFAULT 0.5,
            is_prioritized INTEGER DEFAULT 0,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE
        )
    ''')

    # Risk assessments table (process-risk combinations)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS risk_assessments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL,
            process_id INTEGER NOT NULL,
            risk_id INTEGER NOT NULL,
            vulnerability REAL DEFAULT 0.5,
            resilience REAL DEFAULT 0.3,
            expected_downtime INTEGER DEFAULT 5,
            notes TEXT,
            assessed_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE,
            FOREIGN KEY (process_id) REFERENCES client_processes(id) ON DELETE CASCADE,
            FOREIGN KEY (risk_id) REFERENCES client_risks(id) ON DELETE CASCADE,
            UNIQUE(client_id, process_id, risk_id)
        )
    ''')

    # External data cache table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS external_data_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_name TEXT NOT NULL,
            category TEXT,
            data_key TEXT NOT NULL,
            data_value TEXT,
            numeric_value REAL,
            fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP,
            UNIQUE(source_name, data_key)
        )
    ''')

    conn.commit()
    conn.close()

    return True


# =============================================================================
# CLIENT OPERATIONS
# =============================================================================

def create_client(name, location="", industry="", revenue=0, employees=0,
                  currency="EUR", export_percentage=0, primary_markets="",
                  sectors="", notes=""):
    """Create a new client."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO clients (name, location, industry, revenue, employees,
                            currency, export_percentage, primary_markets, sectors, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (name, location, industry, revenue, employees, currency,
          export_percentage, primary_markets, sectors, notes))

    client_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return client_id


def get_all_clients():
    """Get all clients."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM clients ORDER BY updated_at DESC')
    clients = [dict(row) for row in cursor.fetchall()]

    conn.close()
    return clients


def get_client(client_id):
    """Get a specific client by ID."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM clients WHERE id = ?', (client_id,))
    row = cursor.fetchone()

    conn.close()
    return dict(row) if row else None


def update_client(client_id, **kwargs):
    """Update client information."""
    conn = get_connection()
    cursor = conn.cursor()

    # Build update query dynamically
    fields = []
    values = []
    for key, value in kwargs.items():
        if key not in ['id', 'created_at']:
            fields.append(f"{key} = ?")
            values.append(value)

    fields.append("updated_at = ?")
    values.append(datetime.now().isoformat())
    values.append(client_id)

    query = f"UPDATE clients SET {', '.join(fields)} WHERE id = ?"
    cursor.execute(query, values)

    conn.commit()
    conn.close()

    return True


def delete_client(client_id):
    """Delete a client and all associated data."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('DELETE FROM clients WHERE id = ?', (client_id,))

    conn.commit()
    conn.close()

    return True


# =============================================================================
# PROCESS OPERATIONS
# =============================================================================

def add_client_process(client_id, process_id, process_name, custom_name="",
                       category="", criticality_per_day=0, notes=""):
    """Add a process to a client."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO client_processes (client_id, process_id, process_name,
                                      custom_name, category, criticality_per_day, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (client_id, process_id, process_name, custom_name, category,
          criticality_per_day, notes))

    process_db_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return process_db_id


def get_client_processes(client_id):
    """Get all processes for a client."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT * FROM client_processes
        WHERE client_id = ?
        ORDER BY criticality_per_day DESC
    ''', (client_id,))

    processes = [dict(row) for row in cursor.fetchall()]

    conn.close()
    return processes


def update_client_process(process_db_id, **kwargs):
    """Update a client process."""
    conn = get_connection()
    cursor = conn.cursor()

    fields = []
    values = []
    for key, value in kwargs.items():
        if key not in ['id', 'client_id', 'created_at']:
            fields.append(f"{key} = ?")
            values.append(value)

    values.append(process_db_id)

    query = f"UPDATE client_processes SET {', '.join(fields)} WHERE id = ?"
    cursor.execute(query, values)

    conn.commit()
    conn.close()

    return True


def delete_client_process(process_db_id):
    """Delete a client process."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('DELETE FROM client_processes WHERE id = ?', (process_db_id,))

    conn.commit()
    conn.close()

    return True


# =============================================================================
# RISK OPERATIONS
# =============================================================================

def add_client_risk(client_id, risk_id, risk_name, domain="", category="",
                    probability=0.5, is_prioritized=0, notes=""):
    """Add a risk to a client's risk portfolio."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        INSERT OR REPLACE INTO client_risks
        (client_id, risk_id, risk_name, domain, category, probability, is_prioritized, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (client_id, risk_id, risk_name, domain, category, probability,
          is_prioritized, notes))

    risk_db_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return risk_db_id


def get_client_risks(client_id, prioritized_only=False):
    """Get all risks for a client."""
    conn = get_connection()
    cursor = conn.cursor()

    if prioritized_only:
        cursor.execute('''
            SELECT * FROM client_risks
            WHERE client_id = ? AND is_prioritized = 1
            ORDER BY probability DESC
        ''', (client_id,))
    else:
        cursor.execute('''
            SELECT * FROM client_risks
            WHERE client_id = ?
            ORDER BY probability DESC
        ''', (client_id,))

    risks = [dict(row) for row in cursor.fetchall()]

    conn.close()
    return risks


def update_client_risk(risk_db_id, **kwargs):
    """Update a client risk."""
    conn = get_connection()
    cursor = conn.cursor()

    fields = []
    values = []
    for key, value in kwargs.items():
        if key not in ['id', 'client_id', 'created_at']:
            fields.append(f"{key} = ?")
            values.append(value)

    values.append(risk_db_id)

    query = f"UPDATE client_risks SET {', '.join(fields)} WHERE id = ?"
    cursor.execute(query, values)

    conn.commit()
    conn.close()

    return True


# =============================================================================
# ASSESSMENT OPERATIONS
# =============================================================================

def save_assessment(client_id, process_id, risk_id, vulnerability,
                    resilience, expected_downtime, notes=""):
    """Save or update a risk assessment."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        INSERT OR REPLACE INTO risk_assessments
        (client_id, process_id, risk_id, vulnerability, resilience,
         expected_downtime, notes, assessed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (client_id, process_id, risk_id, vulnerability, resilience,
          expected_downtime, notes, datetime.now().isoformat()))

    conn.commit()
    conn.close()

    return True


def get_assessments(client_id):
    """Get all assessments for a client with process and risk details."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT
            ra.*,
            cp.process_name,
            cp.custom_name,
            cp.criticality_per_day,
            cp.category as process_category,
            cr.risk_name,
            cr.domain,
            cr.category as risk_category,
            cr.probability
        FROM risk_assessments ra
        JOIN client_processes cp ON ra.process_id = cp.id
        JOIN client_risks cr ON ra.risk_id = cr.id
        WHERE ra.client_id = ?
        ORDER BY cp.criticality_per_day DESC, cr.probability DESC
    ''', (client_id,))

    assessments = [dict(row) for row in cursor.fetchall()]

    conn.close()
    return assessments


def get_assessment(client_id, process_id, risk_id):
    """Get a specific assessment."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT * FROM risk_assessments
        WHERE client_id = ? AND process_id = ? AND risk_id = ?
    ''', (client_id, process_id, risk_id))

    row = cursor.fetchone()

    conn.close()
    return dict(row) if row else None


# =============================================================================
# CALCULATION HELPERS
# =============================================================================

def calculate_risk_exposure(criticality, vulnerability, resilience,
                           downtime, probability):
    """
    Calculate risk exposure using PRISM formula.

    Risk Exposure (€/yr) = Criticality × Vulnerability × (1 - Resilience) × Downtime × Probability
    """
    return criticality * vulnerability * (1 - resilience) * downtime * probability


def get_risk_exposure_summary(client_id):
    """Get comprehensive risk exposure summary for a client."""
    assessments = get_assessments(client_id)

    if not assessments:
        return None

    summary = {
        "total_exposure": 0,
        "by_domain": {},
        "by_process": {},
        "by_risk": {},
        "assessments": []
    }

    for a in assessments:
        exposure = calculate_risk_exposure(
            a['criticality_per_day'],
            a['vulnerability'],
            a['resilience'],
            a['expected_downtime'],
            a['probability']
        )

        # Add to total
        summary["total_exposure"] += exposure

        # Add to domain breakdown
        domain = a['domain']
        if domain not in summary["by_domain"]:
            summary["by_domain"][domain] = 0
        summary["by_domain"][domain] += exposure

        # Add to process breakdown
        process_name = a['custom_name'] or a['process_name']
        if process_name not in summary["by_process"]:
            summary["by_process"][process_name] = 0
        summary["by_process"][process_name] += exposure

        # Add to risk breakdown
        risk_name = a['risk_name']
        if risk_name not in summary["by_risk"]:
            summary["by_risk"][risk_name] = 0
        summary["by_risk"][risk_name] += exposure

        # Add to detailed list
        summary["assessments"].append({
            **a,
            "exposure": exposure
        })

    return summary


# Initialize database on module import
init_database()
