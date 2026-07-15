"""Static reference data for the synthetic banking ecosystem.

Kept separate from generation logic so the "shape" of the miniature bank is easy to
read and tune. All money is in INR.
"""
from __future__ import annotations

from app.models.enums import (
    AccountType,
    Criticality,
    CustomerType,
    DataSensitivity,
    EndpointCategory,
)

# ---------------------------------------------------------------- geography
# (name, country, lat, lon, foreign?)
DOMESTIC_CITIES = [
    ("New Delhi", "India", 28.6139, 77.2090),
    ("Mumbai", "India", 19.0760, 72.8777),
    ("Bengaluru", "India", 12.9716, 77.5946),
    ("Chennai", "India", 13.0827, 80.2707),
    ("Kolkata", "India", 22.5726, 88.3639),
    ("Hyderabad", "India", 17.3850, 78.4867),
    ("Pune", "India", 18.5204, 73.8567),
    ("Ahmedabad", "India", 23.0225, 72.5714),
    ("Jaipur", "India", 26.9124, 75.7873),
    ("Faridabad", "India", 28.4089, 77.3178),
]

# High-risk foreign origins used by attack scenarios.
FOREIGN_CITIES = [
    ("Moscow", "Russia", 55.7558, 37.6173),
    ("Kyiv", "Ukraine", 50.4501, 30.5234),
    ("Lagos", "Nigeria", 6.5244, 3.3792),
    ("Bucharest", "Romania", 44.4268, 26.1025),
    ("Shenzhen", "China", 22.5431, 114.0579),
]

DOMESTIC_ISPS = ["Airtel Broadband", "Jio Fiber", "BSNL", "ACT Fibernet", "Hathway"]
HOSTING_ISPS = ["M247 Europe", "DigitalOcean LLC", "Selectel Hosting", "OVH SAS"]

# ---------------------------------------------------------------- devices
DEVICE_POOL = {
    "mobile": [
        ("Android 14", "Chrome Mobile 126", "Samsung"),
        ("Android 13", "Chrome Mobile 125", "OnePlus"),
        ("iOS 17.5", "Mobile Safari 17", "Apple"),
        ("iOS 16.6", "Mobile Safari 16", "Apple"),
    ],
    "desktop": [
        ("Windows 11", "Chrome 126", "Dell"),
        ("Windows 11", "Edge 126", "HP"),
        ("macOS 14.5", "Safari 17", "Apple"),
        ("Windows 10", "Firefox 127", "Lenovo"),
    ],
}

# ---------------------------------------------------------------- customers
# type, weight, (balance_min, balance_max), (txn_min, txn_max), txns_per_day,
# preferred_hours, device_category, accounts, account_types
ARCHETYPES = [
    dict(type=CustomerType.STUDENT, weight=5, balance=(2_000, 45_000),
         txn=(120, 3_500), per_day=0.6, hours=[18, 19, 20, 21, 22, 23],
         device="mobile", accounts=1, acct_types=[AccountType.SAVINGS]),
    dict(type=CustomerType.SALARIED, weight=9, balance=(25_000, 6_00_000),
         txn=(500, 45_000), per_day=1.3, hours=[8, 9, 13, 19, 20, 21, 22],
         device="mobile", accounts=2, acct_types=[AccountType.SALARY, AccountType.SAVINGS]),
    dict(type=CustomerType.RETAIL, weight=7, balance=(10_000, 3_50_000),
         txn=(200, 25_000), per_day=0.9, hours=[9, 10, 11, 17, 18, 19, 20],
         device="mobile", accounts=1, acct_types=[AccountType.SAVINGS]),
    dict(type=CustomerType.BUSINESS, weight=4, balance=(3_00_000, 60_00_000),
         txn=(5_000, 6_00_000), per_day=3.0, hours=[10, 11, 12, 14, 15, 16, 17, 18],
         device="desktop", accounts=2, acct_types=[AccountType.CURRENT, AccountType.BUSINESS]),
    dict(type=CustomerType.PREMIUM, weight=3, balance=(6_00_000, 1_20_00_000),
         txn=(10_000, 12_00_000), per_day=1.8, hours=[8, 9, 10, 20, 21, 22],
         device="mobile", accounts=2, acct_types=[AccountType.SAVINGS, AccountType.INVESTMENT]),
    dict(type=CustomerType.CORPORATE, weight=2, balance=(50_00_000, 40_00_00_000),
         txn=(1_00_000, 2_50_00_000), per_day=5.0, hours=[9, 10, 11, 12, 14, 15, 16, 17],
         device="desktop", accounts=3,
         acct_types=[AccountType.CURRENT, AccountType.TREASURY, AccountType.BUSINESS]),
    dict(type=CustomerType.HNWI, weight=2, balance=(80_00_000, 90_00_00_000),
         txn=(1_00_000, 60_00_000), per_day=1.4, hours=[10, 11, 12, 21, 22],
         device="mobile", accounts=2, acct_types=[AccountType.SAVINGS, AccountType.INVESTMENT]),
]

FIRST_NAMES = [
    "Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Sai", "Reyansh", "Ayaan",
    "Krishna", "Ishaan", "Ananya", "Diya", "Aadhya", "Saanvi", "Priya", "Riya",
    "Anika", "Navya", "Meera", "Kavya", "Rohan", "Karan", "Nisha", "Pooja",
    "Rahul", "Sneha", "Vikram", "Neha", "Amit", "Deepa",
]
LAST_NAMES = [
    "Sharma", "Verma", "Gupta", "Iyer", "Reddy", "Nair", "Patel", "Singh",
    "Mehta", "Bose", "Kapoor", "Chopra", "Malhotra", "Das", "Rao",
]

# Transaction categories weighted by "normal" retail behaviour.
TXN_CATEGORIES = [
    ("bill_payment", "bill_payment", 0.22),
    ("card_payment", "card_payment", 0.28),
    ("transfer", "transfer", 0.30),
    ("atm_withdrawal", "atm_withdrawal", 0.10),
    ("subscription", "bill_payment", 0.06),
    ("investment", "transfer", 0.04),
]

# ---------------------------------------------------------------- infrastructure
# ref, name, category, criticality, data_sensitivity, encryption_profile, weak?
ENDPOINTS = [
    ("EP-AUTH-01", "Authentication Service", EndpointCategory.AUTH,
     Criticality.CRITICAL, DataSensitivity.CREDENTIALS, "TLS1.3-AES256-GCM", False),
    ("EP-PAY-01", "Payments API Gateway", EndpointCategory.PAYMENT_API,
     Criticality.CRITICAL, DataSensitivity.CARDHOLDER, "TLS1.3-AES256-GCM", False),
    ("EP-PAY-LEGACY", "Legacy Payments Processor", EndpointCategory.PAYMENT_API,
     Criticality.CRITICAL, DataSensitivity.CARDHOLDER, "TLS1.0-3DES-CBC (Sweet32)", True),
    ("EP-PORTAL-01", "Retail Net-Banking Portal", EndpointCategory.PORTAL,
     Criticality.HIGH, DataSensitivity.PII, "TLS1.2-ECDHE-RSA", False),
    ("EP-MOB-01", "Mobile Banking Backend", EndpointCategory.MOBILE,
     Criticality.HIGH, DataSensitivity.BALANCES, "TLS1.3-AES256-GCM", False),
    ("EP-TXN-01", "Core Transaction Processing", EndpointCategory.TXN_PROCESSING,
     Criticality.CRITICAL, DataSensitivity.FINANCIAL, "TLS1.3-AES256-GCM", False),
    ("EP-ADMIN-01", "Internal Admin Console", EndpointCategory.ADMIN,
     Criticality.HIGH, DataSensitivity.ADMIN, "TLS1.3-AES256-GCM", False),
    ("EP-CUSTDB-01", "Customer Records Database", EndpointCategory.CUSTOMER_DB,
     Criticality.CRITICAL, DataSensitivity.PII, "TLS1.3-AES256-GCM", False),
    ("EP-CARD-01", "Card Processing System", EndpointCategory.CARD_PROCESSING,
     Criticality.CRITICAL, DataSensitivity.CARDHOLDER, "TLS1.2-ECDHE-RSA", False),
    ("EP-NOTIF-01", "Customer Notification Service", EndpointCategory.NOTIFICATION,
     Criticality.LOW, DataSensitivity.CONTACT, "TLS1.2-ECDHE-RSA", False),
    ("EP-CRYPTO-01", "Encryption Gateway (RSA-2048)", EndpointCategory.ENCRYPTION_GATEWAY,
     Criticality.CRITICAL, DataSensitivity.CRYPTO_MATERIAL, "RSA-2048 / ECDHE", False),
]

# Endpoints a normal retail transaction can traverse.
TXN_ENDPOINT_REFS = ["EP-PAY-01", "EP-PAY-LEGACY", "EP-MOB-01", "EP-TXN-01", "EP-CARD-01"]
AUTH_ENDPOINT_REFS = ["EP-AUTH-01", "EP-PORTAL-01", "EP-MOB-01"]
