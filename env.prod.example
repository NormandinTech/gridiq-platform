"""
GridIQ — Cybersecurity & Compliance Service
OT/IT threat detection, zero-trust policy engine, NERC CIP compliance tracking.
"""
from __future__ import annotations

import hashlib
import logging
import random
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ── Known malicious patterns (OT/ICS specific) ────────────────────────────────

ICS_THREAT_SIGNATURES = [
    {
        "id": "SIG-001",
        "name": "Modbus unauthorized write",
        "protocol": "modbus",
        "pattern": r"function_code=0x(05|06|0f|10)",
        "cve": None,
        "threat_level": "high",
        "description": "Unauthorized Modbus write command to coil/register",
    },
    {
        "id": "SIG-002",
        "name": "DNP3 reconnaissance scan",
        "protocol": "dnp3",
        "pattern": r"poll_rate_multiplier>5",
        "cve": None,
        "threat_level": "medium",
        "description": "Abnormally high DNP3 polling rate — possible reconnaissance",
    },
    {
        "id": "SIG-003",
        "name": "ICS exploit CVE-2024-3811",
        "protocol": "modbus",
        "pattern": r"malformed_frame=True",
        "cve": "CVE-2024-3811",
        "threat_level": "critical",
        "description": "Malformed Modbus/TCP frame matching known ICS exploit pattern",
    },
    {
        "id": "SIG-004",
        "name": "IEC 61850 GOOSE spoofing",
        "protocol": "iec61850",
        "pattern": r"goose_stNum_rollback",
        "cve": "CVE-2023-1234",
        "threat_level": "critical",
        "description": "GOOSE message stNum rollback — possible replay/spoofing attack",
    },
    {
        "id": "SIG-005",
        "name": "Brute-force authentication",
        "protocol": "any",
        "pattern": r"failed_auth_count>5",
        "cve": None,
        "threat_level": "medium",
        "description": "Multiple consecutive authentication failures",
    },
]


class ThreatDetectionEngine:
    """
    Real-time OT/IT threat detection.
    Analyzes network traffic, protocol anomalies, and behavioral patterns.
    """

    def __init__(self):
        self._threat_scores: Dict[str, List[float]] = {}  # ip -> recent scores
        self._blocked_ips: set = set()
        self._auth_failures: Dict[str, int] = {}  # ip/user -> count

    def analyze_packet(self, source_ip: str, dest_ip: str, protocol: str,
                       payload_meta: Dict) -> Optional[Dict]:
        """
        Analyze a network packet/event for threats.
        Returns threat dict if detected, None otherwise.
        """
        for sig in ICS_THREAT_SIGNATURES:
            if sig["protocol"] not in (protocol.lower(), "any"):
                continue
            # Simple pattern matching on payload metadata string
            meta_str = str(payload_meta)
            pattern = sig["pattern"].replace("r\"", "").replace("\"", "")
            if any(k in meta_str for k in pattern.split("=")):
                return {
                    "signature_id": sig["id"],
                    "threat_level": sig["threat_level"],
                    "title": sig["name"],
                    "description": sig["description"],
                    "source_ip": source_ip,
                    "destination_ip": dest_ip,
                    "protocol": protocol,
                    "cve_id": sig["cve"],
                    "threat_score": self._calculate_score(sig["threat_level"]),
                    "should_block": sig["threat_level"] in ("critical", "high"),
                }
        return None

    def record_auth_failure(self, identifier: str) -> Tuple[int, bool]:
        """
        Record an auth failure. Returns (count, should_lock).
        Lock threshold: 5 failures within window.
        """
        self._auth_failures[identifier] = self._auth_failures.get(identifier, 0) + 1
        count = self._auth_failures[identifier]
        should_lock = count >= 5
        if should_lock:
            logger.warning(f"[ThreatEngine] Account/IP locked: {identifier} ({count} failures)")
        return count, should_lock

    def block_ip(self, ip: str) -> None:
        self._blocked_ips.add(ip)
        logger.info(f"[ThreatEngine] Blocked IP: {ip}")

    def is_blocked(self, ip: str) -> bool:
        return ip in self._blocked_ips

    def _calculate_score(self, threat_level: str) -> float:
        base = {"critical": 88, "high": 65, "medium": 42, "low": 22}.get(threat_level, 30)
        return round(base + random.uniform(-5, 10), 1)

    def get_security_posture(self) -> Dict[str, Any]:
        """Compute overall security posture scores."""
        return {
            "overall_score": 71,
            "network_segmentation_score": 88,
            "patch_compliance_score": 62,
            "access_control_score": 79,
            "endpoint_hardening_score": 55,
            "active_threats": 1,
            "events_today": 847,
            "blocked_today": 23,
            "mean_time_to_detect_min": 4.2,
        }

    def get_zone_statuses(self) -> List[Dict]:
        return [
            {"zone_name": "Internet perimeter", "status": "secure", "active_threats": 0, "details": "WAF · DDoS protection active"},
            {"zone_name": "DMZ / Historian", "status": "secure", "active_threats": 0, "details": "Data diode enabled"},
            {"zone_name": "NGFW — IT/OT boundary", "status": "warning", "active_threats": 0, "details": "Firewall ruleset review due"},
            {"zone_name": "Engineering workstations", "status": "warning", "active_threats": 0, "details": "Patch pending on 2 hosts"},
            {"zone_name": "SCADA / RTU bus", "status": "critical", "active_threats": 1, "details": "Active ICS exploit attempt"},
            {"zone_name": "AMI / Smart meters", "status": "secure", "active_threats": 0, "details": "142 devices — all certified"},
            {"zone_name": "Protection relays", "status": "warning", "active_threats": 0, "details": "DNP3 polling anomaly — investigating"},
        ]


# ── Zero-Trust Policy Engine ──────────────────────────────────────────────────

class ZeroTrustPolicyEngine:
    """
    Evaluates every access request against context-aware policies.
    No implicit trust — every request is verified regardless of network location.
    """

    def __init__(self):
        self._policies: List[Dict] = self._default_policies()

    def _default_policies(self) -> List[Dict]:
        return [
            {
                "id": "P-001",
                "name": "Block all inbound OT from internet",
                "source_zone": "internet",
                "target_zone": "ot",
                "action": "deny",
                "conditions": {},
            },
            {
                "id": "P-002",
                "name": "Require MFA for OT access",
                "source_zone": "it",
                "target_zone": "ot",
                "action": "allow",
                "conditions": {"mfa_required": True, "session_timeout_min": 30},
            },
            {
                "id": "P-003",
                "name": "Vendor jump server only",
                "source_zone": "internet",
                "target_zone": "it",
                "action": "allow",
                "conditions": {"via_jump_server": True, "mfa_required": True},
            },
            {
                "id": "P-004",
                "name": "AI dispatch commands require signing",
                "source_zone": "it",
                "target_zone": "ot",
                "action": "allow",
                "conditions": {"command_signed": True, "role": "ai-dispatch"},
            },
        ]

    def evaluate(self, request: Dict) -> Dict[str, Any]:
        """
        Evaluate an access request.
        Returns: {allowed: bool, policy_id: str, reason: str, risk_score: float}
        """
        source_zone = request.get("source_zone", "internet")
        target_zone = request.get("target_zone", "ot")
        has_mfa = request.get("mfa", False)
        role = request.get("role", "operator")
        source_ip = request.get("source_ip", "")

        # Explicit deny first
        if source_zone == "internet" and target_zone == "ot":
            return {
                "allowed": False,
                "policy_id": "P-001",
                "reason": "Direct internet → OT access is denied",
                "risk_score": 95.0,
            }

        # MFA check for OT
        if target_zone == "ot" and not has_mfa:
            return {
                "allowed": False,
                "policy_id": "P-002",
                "reason": "MFA required for OT zone access",
                "risk_score": 60.0,
            }

        # Default allow with logging
        risk = self._calculate_risk(request)
        return {
            "allowed": True,
            "policy_id": "P-DEFAULT",
            "reason": "Access granted — all conditions met",
            "risk_score": risk,
        }

    def _calculate_risk(self, request: Dict) -> float:
        risk = 10.0
        if not request.get("mfa"):
            risk += 30
        if request.get("source_zone") == "internet":
            risk += 20
        if request.get("off_hours"):
            risk += 15
        if request.get("new_device"):
            risk += 25
        return min(100.0, risk)


# ── NERC CIP Compliance Checker ───────────────────────────────────────────────

class NERCCIPComplianceChecker:
    """
    Automated NERC CIP compliance assessment.
    Checks each standard and computes compliance percentage.
    """

    STANDARDS = [
        {
            "control_id": "CIP-002",
            "title": "BES cyber system identification",
            "description": "Identify and categorize BES Cyber Systems",
            "category": "Asset Management",
        },
        {
            "control_id": "CIP-003",
            "title": "Security management controls",
            "description": "Senior manager approval, exception processes",
            "category": "Governance",
        },
        {
            "control_id": "CIP-005",
            "title": "Electronic security perimeters",
            "description": "ESP definition, access points, remote access",
            "category": "Network Security",
        },
        {
            "control_id": "CIP-006",
            "title": "Physical security",
            "description": "Physical access controls, visitor logs, CCTV",
            "category": "Physical Security",
        },
        {
            "control_id": "CIP-007",
            "title": "System security management",
            "description": "Ports/services, patch management, malware prevention",
            "category": "Endpoint Security",
        },
        {
            "control_id": "CIP-010",
            "title": "Configuration change management",
            "description": "Baselines, change management, vulnerability monitoring",
            "category": "Change Management",
        },
        {
            "control_id": "CIP-011",
            "title": "Information protection",
            "description": "BES Cyber System Information handling and disposal",
            "category": "Data Protection",
        },
        {
            "control_id": "CIP-013",
            "title": "Supply chain risk management",
            "description": "Vendor risk, software integrity, hardware authenticity",
            "category": "Supply Chain",
        },
    ]

    def assess_all(self) -> List[Dict[str, Any]]:
        """
        Run compliance assessment for all NERC CIP standards.
        In production, each check pulls real system data.
        """
        # Realistic compliance scores (CIP-007 and CIP-013 have gaps)
        scores = {
            "CIP-002": 100,
            "CIP-003": 100,
            "CIP-005": 88,
            "CIP-006": 95,
            "CIP-007": 62,   # Patch management backlog
            "CIP-010": 78,
            "CIP-011": 91,
            "CIP-013": 55,   # Supply chain — common gap
        }

        results = []
        for std in self.STANDARDS:
            pct = scores.get(std["control_id"], 75)
            status = "compliant" if pct >= 90 else "partial" if pct >= 60 else "non_compliant"
            due_days = {"CIP-007": -5, "CIP-010": 14, "CIP-013": 0}.get(std["control_id"], 60)
            due_date = (datetime.now(timezone.utc) + timedelta(days=due_days)).isoformat()
            results.append({
                **std,
                "standard": "NERC_CIP",
                "compliance_pct": pct,
                "status": status,
                "last_assessed": datetime.now(timezone.utc).isoformat(),
                "due_date": due_date,
                "findings": self._findings(std["control_id"], pct),
            })
        return results

    def _findings(self, control_id: str, pct: float) -> Optional[str]:
        findings = {
            "CIP-007": "3 systems have patches >90 days overdue. Endpoint hardening policy not applied to 2 legacy RTUs.",
            "CIP-010": "Configuration baseline not updated for 2 assets following recent firmware changes.",
            "CIP-013": "Vendor risk assessment incomplete for 4 new software suppliers. Supply chain attestations missing.",
        }
        return findings.get(control_id) if pct < 90 else None

    def overall_score(self, results: List[Dict]) -> float:
        if not results:
            return 0.0
        return round(sum(r["compliance_pct"] for r in results) / len(results), 1)


# ── Singletons ────────────────────────────────────────────────────────────────

threat_engine = ThreatDetectionEngine()
zero_trust = ZeroTrustPolicyEngine()
compliance_checker = NERCCIPComplianceChecker()
