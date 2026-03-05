#!/usr/bin/env python3
"""Supplement example artifacts for remaining unmapped objectives."""

import sqlite3
import os

DB_PATH = os.environ.get("DB_PATH", os.path.join(os.path.dirname(__file__), "cmmc.db"))

SUPPLEMENT = {
    "3.1.1[f]": "Device/system access enforcement evidence | NAC logs blocking unauthorized devices, 802.1X rejection logs, MDM compliance reports showing non-compliant devices blocked",
    "3.1.3[c]": "Designated CUI source/destination definitions | Data flow diagrams showing approved CUI paths, DLP policy defining allowed endpoints/networks for CUI transfer",
    "3.1.3[d]": "CUI flow control authorizations | Approved data transfer matrix, information flow policy, DLP rules defining allowed CUI movements",
    "3.1.3[e]": "CUI flow control enforcement | DLP alerts/blocks for unauthorized transfers, firewall rules enforcing approved data flows, email gateway rules restricting CUI",
    "3.1.4[c]": "Separated accounts for duty separation | AD showing separate accounts for conflicting roles, no single user in both approver and executor groups",
    "3.1.5[d]": "Security function access authorization | List of users authorized for security functions, approval records, access control matrix for security tools/consoles",
    "3.1.7[c]": "Non-privileged user restriction enforcement | UAC blocking elevation attempts, sudo denials in logs, application role restrictions preventing privileged actions",
    "3.1.7[d]": "Privileged function audit logs | Windows Event 4672/4673 logs, sudo command logs, SIEM alerts for privileged operations, PAM session recordings",
    "3.1.10[c]": "Pattern-hiding display enforcement | Screensaver with password showing no data, lock screen screenshots, GPO enforcing pattern-hiding display",
    "3.1.12[c]": "Remote access session control mechanisms | VPN session limits, concurrent session restrictions, session recording for remote admin access",
    "3.1.12[d]": "Remote access session monitoring | VPN session logs reviewed regularly, SIEM alerts for anomalous remote sessions, remote access usage reports",
    "3.1.15[c]": "Remote privileged command authorization | Approval records for remote admin commands, authorized remote admin personnel list, PAM policy for remote privileged access",
    "3.1.15[d]": "Remote security information access authorization | Approval for remote access to security logs/configs, authorized personnel for remote security admin, jump server access logs",
    "3.1.20[c]": "External system connection verification | Interconnection security agreement (ISA) compliance checks, external system security posture verification records",
    "3.1.20[d]": "External system use verification | External system authorization records, approved external system list with verification dates, user acknowledgment of external system risks",
    "3.1.20[e]": "External connection controls/limits | Firewall rules limiting external connections, proxy configurations for external access, bandwidth/access time restrictions",
    "3.1.20[f]": "External system use controls/limits | Policy limiting what CUI can be processed on external systems, DLP preventing CUI transfer to unauthorized external systems",
    "3.1.21[c]": "Portable storage use limitation on external systems | DLP policy blocking CUI transfer to removable media on external systems, policy prohibiting organizational USB on non-org systems",
    "3.1.22[c]": "Public content review process | Content approval workflow documentation, review checklist before public posting, designated content reviewers",
    "3.1.22[d]": "Public content CUI review | Records of content reviews checking for CUI, automated scanning for CUI markers in public content, review sign-off records",
    "3.1.22[e]": "Improper CUI posting remediation | Takedown procedures for CUI found on public systems, incident records of CUI removal from public sites, monitoring for CUI exposure",
    "3.2.1[d]": "Policy/standards awareness evidence | Training materials covering applicable policies and standards, user acknowledgment forms for security policies, quiz/test results on policy knowledge",
    "3.3.1[d]": "Audit record content verification | Sample audit records showing required fields (who, what, when, where, outcome), SIEM parsing rules extracting all required fields",
    "3.3.1[e]": "Retention requirements documentation | Audit log retention policy (typically 1+ years for CMMC), retention settings in SIEM/log management, data lifecycle policy",
    "3.3.1[f]": "Audit record retention evidence | SIEM storage configuration showing retention period, archived log files with dates proving retention, backup of audit records",
    "3.3.3[c]": "Audit event type updates | Records of log review findings leading to new event types being audited, change requests to add/modify audited events",
    "3.3.4[c]": "Audit failure alert recipients | Alert configuration showing designated personnel receive audit failure notifications, distribution list for audit alerts, escalation procedures",
    "3.3.7[c]": "Time synchronization evidence | NTP client configuration on systems, time comparison reports across systems, NTP server sync status screenshots",
    "3.3.8[c]": "Audit log deletion protection | Immutable log storage configuration, write-once media, SIEM retention locks, file permissions preventing deletion by non-admins",
    "3.3.8[d]": "Audit tool access protection | Access control on SIEM/log management consoles, admin account list for logging tools, MFA for log management access",
    "3.3.8[e]": "Audit tool modification protection | Change management records for logging tool changes, file integrity monitoring on audit tools, configuration baselines for logging systems",
    "3.3.8[f]": "Audit tool deletion protection | Backup of audit tools, protected installation directories, admin-only uninstall permissions for security tools",
    "3.4.1[d]": "System inventory | Hardware and software inventory spreadsheet or CMDB export, asset management tool report | CMDB, asset management tool (Lansweeper, SCCM, Snipe-IT)",
    "3.4.1[e]": "Comprehensive inventory contents | Inventory showing hardware (servers, workstations, network devices), software (OS, applications), firmware versions, and system documentation references",
    "3.4.1[f]": "Inventory maintenance evidence | Dated inventory versions showing updates, inventory review records, automated discovery scan results compared to inventory",
    "3.4.3[d]": "Change logging evidence | Change management system logs, configuration change audit trails, version control history for configuration files",
    "3.4.5[d]": "Physical access restriction enforcement | Server room badge logs correlated with change windows, locked cabinet access logs during maintenance",
    "3.4.5[e]": "Logical access restriction definitions | Documented access requirements for making system changes, role-based access for configuration management tools",
    "3.4.5[f]": "Logical access restriction documentation | Access control matrix for configuration management, documented approval requirements for system changes",
    "3.4.5[g]": "Logical access restriction approvals | Approved access requests for configuration management tools, management authorization records",
    "3.4.5[h]": "Logical access restriction enforcement | Configuration management tool access controls, screenshots of restricted admin access, change management approval workflow enforced by tooling",
    "3.4.7[c]": "Non-essential program restriction enforcement | AppLocker/WDAC block logs, GPO preventing unauthorized software execution, endpoint protection blocking unauthorized apps",
    "3.4.7[d]": "Essential functions definition | Documented list of essential system functions per system type, approved function baseline",
    "3.4.7[e]": "Non-essential functions definition | List of functions identified as non-essential, justification for disabling/restricting each",
    "3.4.7[f]": "Non-essential function restriction enforcement | Disabled service screenshots, configuration showing non-essential functions removed/restricted",
    "3.4.7[g]": "Essential ports definition | Documented list of essential ports per system type, firewall rule justification matrix",
    "3.4.7[h]": "Non-essential ports definition | Port scan results identifying non-essential open ports, ports identified for closure/restriction",
    "3.4.7[i]": "Non-essential port restriction enforcement | Firewall rules blocking non-essential ports, Nessus/Nmap scan showing only essential ports open, host-based firewall configurations",
    "3.4.7[j]": "Essential protocols definition | Documented list of essential protocols (HTTPS, SSH, etc.), protocol usage justification",
    "3.4.7[k]": "Non-essential protocols definition | List of prohibited protocols (Telnet, FTP, SSLv3, etc.), protocol restriction policy",
    "3.4.7[l]": "Non-essential protocol restriction enforcement | Network captures/configs showing prohibited protocols blocked, GPO disabling legacy protocols, firewall protocol filters",
    "3.4.7[m]": "Essential services definition | Documented list of essential services per system role, service baseline per OS/application",
    "3.4.7[n]": "Non-essential services definition | List of services to disable/restrict, comparison of running services vs essential services baseline",
    "3.4.7[o]": "Non-essential service restriction enforcement | Disabled services screenshots (services.msc, systemctl), STIG compliance scan showing disabled unnecessary services",
    "3.4.8[c]": "Application whitelist/blacklist enforcement | AppLocker policy export, WDAC configuration, application control block logs, compliance scan showing enforcement",
    "3.4.9[c]": "Software installation monitoring | Endpoint protection alerts for software installs, SIEM alerts for new software, software inventory change reports",
    "3.5.2[c]": "Device authentication/verification | 802.1X device authentication logs, machine certificate enrollment records, NAC device posture check results",
    "3.5.3[c]": "MFA for privileged network access | MFA configuration for admin VPN/remote access, conditional access policy screenshots requiring MFA for privileged roles, MFA enrollment records for admins",
    "3.5.3[d]": "MFA for non-privileged network access | MFA configuration for standard user VPN/remote access, conditional access policy for all remote users, MFA enrollment status report",
    "3.5.7[c]": "Password complexity enforcement | AD password policy GPO showing minimum length, complexity requirements, password filter configuration",
    "3.5.7[d]": "Password character change enforcement | AD password policy showing minimum password age and history requirements preventing reuse, configuration requiring character changes between passwords",
    "3.6.1[d]": "Incident analysis capability | IR procedures for analysis phase, forensic tools available, analyst training records, sample analysis reports from past incidents",
    "3.6.1[e]": "Incident containment capability | Containment procedures in IR plan, network isolation capabilities, endpoint quarantine procedures, sample containment actions from past incidents",
    "3.6.1[f]": "Incident recovery capability | Recovery procedures in IR plan, backup restoration procedures, system rebuild procedures, sample recovery actions from past incidents",
    "3.6.1[g]": "User response activities | User incident reporting procedures, phishing reporting button/process, user communication templates for incidents, post-incident user notifications",
    "3.6.2[c]": "Reporting authorities identified | List of external reporting requirements (CISA, DIBNet, law enforcement), reporting thresholds and timelines",
    "3.6.2[d]": "Internal reporting officials identified | Internal incident notification chain, management notification procedures, CISO/CIO notification requirements",
    "3.6.2[e]": "External authority notification evidence | Records of incident reports to CISA/DIBNet, reporting templates, evidence of meeting 72-hour reporting requirement",
    "3.6.2[f]": "Internal official notification evidence | Email/ticket records of management notification during incidents, incident briefing records",
    "3.7.2[c]": "Maintenance mechanism controls | Approved maintenance tool list, tool integrity verification records, maintenance tool access restrictions",
    "3.7.2[d]": "Maintenance personnel controls | Authorized maintenance personnel list, background checks for maintenance staff, escort procedures for third-party maintenance",
    "3.8.1[c]": "Paper CUI media storage | Locked filing cabinets/safes for CUI documents, access logs for document storage areas, clean desk policy enforcement",
    "3.8.1[d]": "Digital CUI media storage | Encrypted storage for digital CUI, access-controlled file shares, media safe/vault for removable digital media",
    "3.9.2[c]": "System protection during personnel actions | Temporary access restrictions during transfers, CUI access review upon role changes, system access modification records tied to HR actions",
    "3.10.1[c]": "Equipment physical access controls | Locked server racks, restricted access to networking equipment, badge-controlled equipment rooms",
    "3.10.1[d]": "Operating environment physical access controls | Controlled access to offices containing CUI systems, visitor restrictions in CUI processing areas",
    "3.10.2[c]": "Facility monitoring | CCTV coverage maps, camera placement documentation, monitoring station procedures, recording retention policy",
    "3.10.2[d]": "Support infrastructure monitoring | Monitoring of HVAC, power, cabling infrastructure, physical intrusion detection for utility areas",
    "3.10.5[c]": "Physical access device management | Key inventory and issuance log, badge lifecycle management, combination change records, lost badge/key procedures",
    "3.11.2[d]": "CUI system vulnerability scans | Vulnerability scan reports specifically covering systems that process/store/transmit CUI, scan scope documentation showing CUI system coverage",
    "3.11.2[e]": "Application vulnerability scans | Web application vulnerability scans (OWASP ZAP, Burp Suite), application-specific scan results, scans triggered by new vulnerability disclosures",
    "3.12.2[c]": "POA&M implementation evidence | Closed POA&M items with completion evidence, remediation verification records, milestone completion tracking",
    "3.12.4[c]": "Environment of operation documentation | SSP section describing physical environment, network environment, data flows, interconnections",
    "3.12.4[d]": "Non-applicable requirements documentation | List of requirements marked N/A with justification approved by authorizing official, scoping documentation",
    "3.12.4[e]": "Security implementation descriptions | SSP control implementation statements for each requirement, how each control is implemented in the specific environment",
    "3.12.4[f]": "System interconnection documentation | SSP appendix listing all interconnected systems, ISAs, data flows between systems, trust relationships",
    "3.12.4[g]": "SSP update frequency defined | Policy stating SSP review/update frequency (at least annually and after significant changes)",
    "3.12.4.[h]": "SSP update evidence | Dated SSP versions showing updates at defined frequency, change log in SSP, review sign-off records",
    "3.14.1[d]": "Flaw reporting timeliness | Vulnerability disclosure records with timestamps, time from discovery to report, vulnerability management workflow showing reporting step",
    "3.14.1[e]": "Flaw correction timeframes | Remediation SLA policy (e.g., Critical: 15 days, High: 30 days, Medium: 90 days), documented patching timelines",
    "3.14.1[f]": "Flaw correction evidence | Patch deployment reports showing remediation within SLA, before/after vulnerability scans, exception/risk acceptance for delayed patches",
    "3.14.3[c]": "Advisory response actions | Records of actions taken in response to security advisories, patch deployments triggered by advisories, configuration changes based on advisories, risk acceptance decisions",
}


def seed_supplement():
    conn = sqlite3.connect(DB_PATH)

    updated = 0
    for obj_id, text in SUPPLEMENT.items():
        r = conn.execute(
            "UPDATE objectives SET example_artifacts = ? WHERE id = ? AND (example_artifacts IS NULL OR example_artifacts = '')",
            (text, obj_id)
        )
        if r.rowcount > 0:
            updated += 1

    conn.commit()
    conn.close()
    print(f"Supplemented {updated} additional objectives")


if __name__ == "__main__":
    seed_supplement()
