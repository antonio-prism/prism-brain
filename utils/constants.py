"""
PRISM Brain - Configuration Constants
=====================================
Edit this file to change application settings without modifying code.
"""

# Application Settings
APP_NAME = "PRISM Brain"
APP_VERSION = "1.0.0"
APP_SUBTITLE = "Risk Intelligence System"

# Default Values
DEFAULT_CURRENCY = "EUR"
CURRENCY_SYMBOLS = {
    "EUR": "€",
    "USD": "$",
    "GBP": "£",
    "NOK": "kr"
}

# Risk Domains with colors
RISK_DOMAINS = {
    "PHYSICAL": {"color": "#FFC000", "icon": "🌍", "description": "Climate, Energy, Materials"},
    "STRUCTURAL": {"color": "#5B9BD5", "icon": "🏛️", "description": "Geopolitical, Regulatory, Financial"},
    "OPERATIONAL": {"color": "#70AD47", "icon": "⚙️", "description": "Supply Chain, Labor, Business Continuity"},
    "DIGITAL": {"color": "#7030A0", "icon": "💻", "description": "Cybersecurity, Technology, Data"}
}

# Probability Factor Weights (must sum to 1.0)
PROBABILITY_WEIGHTS = {
    "historical_frequency": 0.30,
    "trend_direction": 0.25,
    "current_conditions": 0.25,
    "geographic_exposure": 0.20
}

# Risk Level Thresholds
RISK_LEVELS = {
    "HIGH": {"min": 0.65, "color": "#FF6B6B", "label": "High Risk"},
    "MEDIUM": {"min": 0.40, "color": "#FFE066", "label": "Medium Risk"},
    "LOW": {"min": 0.0, "color": "#69DB7C", "label": "Low Risk"}
}

# Process Categories (APQC Level 1)
PROCESS_CATEGORIES = {
    "1.0": "Develop Vision and Strategy",
    "2.0": "Develop and Manage Products and Services",
    "3.0": "Market and Sell Products and Services",
    "4.0": "Deliver Physical Products",
    "5.0": "Deliver Services",
    "6.0": "Manage Customer Service",
    "7.0": "Develop and Manage Human Capital",
    "8.0": "Manage Information Technology",
    "9.0": "Manage Financial Resources",
    "10.0": "Acquire, Construct, and Manage Assets",
    "11.0": "Manage Enterprise Risk, Compliance, Remediation, and Resiliency",
    "12.0": "Manage External Relationships",
    "13.0": "Develop and Manage Business Capabilities"
}

# Industry Templates (pre-configured process selections)
INDUSTRY_TEMPLATES = {
    "Manufacturing SME": {
        "description": "Small-medium manufacturing company",
        "default_processes": ["4.0", "2.0", "3.0", "8.0", "9.0"]
    },
    "Defense Contractor": {
        "description": "Defense and aerospace manufacturing",
        "default_processes": ["4.0", "2.0", "11.0", "8.0", "7.0"]
    },
    "Energy & Utilities": {
        "description": "Energy production and distribution",
        "default_processes": ["4.0", "5.0", "10.0", "11.0", "8.0"]
    },
    "Financial Services": {
        "description": "Banking, insurance, investment",
        "default_processes": ["5.0", "9.0", "11.0", "8.0", "6.0"]
    },
    "Technology": {
        "description": "Software and technology services",
        "default_processes": ["2.0", "5.0", "8.0", "3.0", "7.0"]
    },
    "Custom": {
        "description": "Select processes manually",
        "default_processes": []
    }
}

# Database Settings
DATABASE_NAME = "prism_brain.db"

# Export Settings
EXCEL_TEMPLATE_SHEETS = [
    "Dashboard",
    "Process Inventory",
    "Risk Events",
    "Risk Matrix",
    "Risk Heatmap",
    "Methodology"
]

# Pagination
ITEMS_PER_PAGE = 20

# Session timeout (minutes)
SESSION_TIMEOUT = 60
