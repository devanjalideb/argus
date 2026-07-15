"""Controlled vocabularies used across the domain.

Stored as short VARCHARs (portable + human-readable in the DB) rather than native DB
enums, so the schema stays identical on MySQL and SQLite and new values never require a
migration. Terminology is kept identical to the API, frontend and reports.
"""
from __future__ import annotations


# ---- Customers ----
class CustomerType:
    RETAIL = "retail"
    SALARIED = "salaried"
    STUDENT = "student"
    BUSINESS = "business"
    CORPORATE = "corporate"
    PREMIUM = "premium"
    HNWI = "high_net_worth"
    EMPLOYEE = "employee"
    ADMIN = "privileged_admin"


class AccountType:
    SAVINGS = "savings"
    CURRENT = "current"
    SALARY = "salary"
    INVESTMENT = "investment"
    BUSINESS = "business"
    TREASURY = "treasury"


# ---- Infrastructure ----
class EndpointCategory:
    AUTH = "authentication"
    PAYMENT_API = "payment_api"
    PORTAL = "customer_portal"
    MOBILE = "mobile_banking"
    TXN_PROCESSING = "transaction_processing"
    ADMIN = "internal_admin"
    CUSTOMER_DB = "customer_database"
    NOTIFICATION = "notification_service"
    CARD_PROCESSING = "card_processing"
    ENCRYPTION_GATEWAY = "encryption_gateway"


class DataSensitivity:
    PUBLIC = "public"
    CONTACT = "contact_details"
    PII = "pii"
    KYC = "kyc"
    BALANCES = "balances"
    FINANCIAL = "financial_records"
    CREDENTIALS = "authentication_credentials"
    CARDHOLDER = "cardholder_data"
    CRYPTO_MATERIAL = "cryptographic_material"
    ADMIN = "privileged_admin_data"


class Criticality:
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# ---- Events ----
class EventType:
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILURE = "login_failure"
    PASSWORD_RESET = "password_reset"
    MFA_CHALLENGE = "mfa_challenge"
    SESSION_START = "session_start"
    TRANSFER = "transfer"
    WIRE = "wire"
    ATM_WITHDRAWAL = "atm_withdrawal"
    BILL_PAYMENT = "bill_payment"
    CARD_PAYMENT = "card_payment"
    API_REQUEST = "api_request"
    RECORD_ACCESS = "record_access"
    DISCLOSURE = "disclosure"
    ANALYST_ACTION = "analyst_action"


class AuthResult:
    SUCCESS = "success"
    FAILURE = "failure"


class TxnStatus:
    COMPLETED = "completed"
    PENDING = "pending"
    FAILED = "failed"
    REVERSED = "reversed"


class FraudStatus:
    NONE = "none"
    SUSPECTED = "suspected"
    CONFIRMED = "confirmed"
    CLEARED = "cleared"


# ---- Vulnerabilities / disclosures ----
class DisclosureType:
    CVE = "cve"
    WEAK_CIPHER = "weak_cipher"
    CRED_LEAK = "credential_leak"
    VENDOR_BREACH = "vendor_breach"
    API_KEY_LEAK = "api_key_leak"
    QUANTUM_HNDL = "quantum_harvest_now_decrypt_later"


class PatchStatus:
    UNPATCHED = "unpatched"
    IN_PROGRESS = "in_progress"
    PATCHED = "patched"


# ---- Investigations ----
class Severity:
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class InvestigationStatus:
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    CONTAINED = "contained"
    RESOLVED = "resolved"
    CLOSED = "closed"


class InvestigationCategory:
    ACCOUNT_TAKEOVER = "account_takeover"
    CREDENTIAL_STUFFING = "credential_stuffing"
    INSIDER_MISUSE = "insider_misuse"
    API_ABUSE = "api_abuse"
    RETROSPECTIVE_EXPOSURE = "retrospective_exposure"
    QUANTUM_EXPOSURE = "quantum_exposure"


class Engine:
    WATCHTOWER = "watchtower"
    BLAST_RADIUS = "blast_radius"


class LifecycleStage:
    DETECTED = "detected"
    ENRICHED = "enriched"
    UNDER_REVIEW = "under_review"
    ACTIONED = "actioned"
    RESOLVED = "resolved"


class BusinessPriority:
    P1 = "P1"  # executive / immediate
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"


# ---- Evidence ----
class EvidenceCategory:
    BEHAVIOURAL = "behavioural"
    AUTHENTICATION = "authentication"
    TRANSACTION = "transaction"
    INFRASTRUCTURE = "infrastructure"
    VULNERABILITY = "vulnerability"
    HISTORICAL = "historical_context"
    ANALYST_NOTE = "analyst_note"


# ---- Recommendations ----
class RecommendationType:
    FREEZE_ACCOUNT = "freeze_account"
    REVOKE_SESSION = "revoke_session"
    BLOCK_DEVICE = "block_device"
    NOTIFY_FRAUD = "notify_fraud_team"
    ESCALATE = "escalate_investigation"
    NOTIFY_CUSTOMER = "notify_customer"
    ROTATE_CREDENTIALS = "rotate_credentials"
    PATCH_ENDPOINT = "patch_endpoint"
    REGULATORY_REVIEW = "initiate_regulatory_review"
    GENERATE_REPORT = "generate_report"
    CLOSE = "close_investigation"


class RecommendationStatus:
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    POSTPONED = "postponed"
    COMPLETED = "completed"


# ---- Reports ----
class ReportType:
    EXECUTIVE = "executive"
    TECHNICAL = "technical"
    COMPLIANCE = "compliance"
    JSON_EXPORT = "json_export"


class ReportStatus:
    GENERATING = "generating"
    READY = "ready"
    FAILED = "failed"


class ExportFormat:
    PDF = "pdf"
    JSON = "json"
    CSV = "csv"


# ---- Risk Memory ----
class EntityType:
    CUSTOMER = "customer"
    DEVICE = "device"
    IP = "ip_address"
    ACCOUNT = "account"
    ENDPOINT = "endpoint"


# ---- Analysts / auth ----
class Role:
    ANALYST = "analyst"
    MANAGER = "security_manager"
    CISO = "ciso"
    ADMIN = "admin"
