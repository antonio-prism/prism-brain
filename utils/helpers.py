"""
PRISM Brain - Helper Utilities
==============================
Common functions used across the application.
"""

import json
from pathlib import Path
from datetime import datetime

# Data directory
DATA_DIR = Path(__file__).parent.parent / "data"


def load_risk_database():
    """Load the full risk database from JSON."""
    with open(DATA_DIR / "risk_database.json", 'r') as f:
        return json.load(f)


def load_process_framework():
    """Load the APQC process framework from JSON."""
    with open(DATA_DIR / "process_framework.json", 'r') as f:
        return json.load(f)


def load_data_summary():
    """Load the data summary."""
    with open(DATA_DIR / "data_summary.json", 'r') as f:
        return json.load(f)


def get_risk_by_id(risk_id):
    """Get a specific risk by its ID."""
    risks = load_risk_database()
    for risk in risks:
        if risk.get('Event_ID') == risk_id:
            return risk
    return None


def get_risks_by_domain(domain):
    """Get all risks for a specific domain."""
    risks = load_risk_database()
    return [r for r in risks if r.get('Layer_1_Primary') == domain]


def get_super_risks():
    """Get all super risks."""
    risks = load_risk_database()
    return [r for r in risks if r.get('Super_Risk') == 'YES']


def get_processes_by_level(level):
    """Get all processes at a specific hierarchy level."""
    processes = load_process_framework()
    return {k: v for k, v in processes.items() if v.get('depth') == level}


def get_process_children(parent_id):
    """Get child processes of a parent process."""
    processes = load_process_framework()
    children = {}
    parent_prefix = f"{parent_id}."

    for key, value in processes.items():
        if key.startswith(parent_prefix):
            # Only direct children (one level deeper)
            remaining = key[len(parent_prefix):]
            if '.' not in remaining:
                children[key] = value

    return children


def format_currency(amount, currency="EUR"):
    """Format a number as currency."""
    symbols = {"EUR": "€", "USD": "$", "GBP": "£", "NOK": "kr"}
    symbol = symbols.get(currency, currency)

    if amount >= 1_000_000:
        return f"{symbol}{amount/1_000_000:.1f}M"
    elif amount >= 1_000:
        return f"{symbol}{amount/1_000:.1f}K"
    else:
        return f"{symbol}{amount:,.0f}"


def format_percentage(value, decimals=1):
    """Format a decimal as percentage."""
    return f"{value * 100:.{decimals}f}%"


def get_risk_level(probability):
    """Get risk level based on probability."""
    if probability >= 0.65:
        return "HIGH"
    elif probability >= 0.40:
        return "MEDIUM"
    else:
        return "LOW"


def get_risk_level_color(level):
    """Get color for risk level."""
    colors = {
        "HIGH": "#FF6B6B",
        "MEDIUM": "#FFE066",
        "LOW": "#69DB7C"
    }
    return colors.get(level, "#CCCCCC")


def get_domain_color(domain):
    """Get color for a risk domain."""
    colors = {
        "PHYSICAL": "#FFC000",
        "STRUCTURAL": "#5B9BD5",
        "OPERATIONAL": "#70AD47",
        "DIGITAL": "#7030A0"
    }
    return colors.get(domain, "#CCCCCC")


def get_domain_icon(domain):
    """Get icon for a risk domain."""
    icons = {
        "PHYSICAL": "🌍",
        "STRUCTURAL": "🏛️",
        "OPERATIONAL": "⚙️",
        "DIGITAL": "💻"
    }
    return icons.get(domain, "📊")


def calculate_default_criticality(revenue, num_processes):
    """
    Calculate default criticality per day for processes.
    Based on: Revenue / 250 working days / number of processes
    """
    if revenue <= 0 or num_processes <= 0:
        return 0

    daily_revenue = revenue / 250  # Working days per year
    return daily_revenue / num_processes


def filter_risks_by_relevance(risks, client_info):
    """
    Filter and score risks based on relevance to client.
    Returns risks sorted by relevance score.
    """
    # Extract client attributes
    industry = client_info.get('industry', '').lower()
    sectors = client_info.get('sectors', '').lower()
    location = client_info.get('location', '').lower()
    export_pct = client_info.get('export_percentage', 0)

    scored_risks = []

    for risk in risks:
        score = 0

        # Base score from baseline probability
        score += risk.get('base_probability', 0.5) * 10

        # Industry match
        affected = risk.get('Affected_Industries', '').lower()
        if industry and industry in affected:
            score += 5
        if 'all industries' in affected:
            score += 3

        # Sector keywords match
        if sectors:
            for sector in sectors.split(','):
                if sector.strip() in affected:
                    score += 2

        # Geographic match
        geo_scope = risk.get('Geographic_Scope', '').lower()
        if 'global' in geo_scope:
            score += 2
        if 'europe' in location.lower() and 'europe' in geo_scope:
            score += 3

        # Export dependency relevance
        if export_pct > 50:
            if 'shipping' in risk.get('Event_Name', '').lower():
                score += 3
            if 'trade' in risk.get('Event_Name', '').lower():
                score += 2

        # Super risk bonus
        if risk.get('Super_Risk') == 'YES':
            score += 5

        scored_risks.append({
            **risk,
            'relevance_score': score
        })

    # Sort by relevance score
    return sorted(scored_risks, key=lambda x: x['relevance_score'], reverse=True)


def generate_assessment_combinations(processes, risks):
    """
    Generate all process-risk combinations that need assessment.
    Returns list of tuples: (process, risk)
    """
    combinations = []
    for process in processes:
        for risk in risks:
            combinations.append((process, risk))
    return combinations


def export_timestamp():
    """Generate timestamp for export filenames."""
    return datetime.now().strftime("%Y%m%d_%H%M%S")
