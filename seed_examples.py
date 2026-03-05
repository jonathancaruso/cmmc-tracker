#!/usr/bin/env python3
"""Seed example artifacts for all CMMC assessment objectives."""

import sqlite3
import os

DB_PATH = os.environ.get("DB_PATH", os.path.join(os.path.dirname(__file__), "cmmc.db"))

# Map each requirement to example artifacts and sources
# Format: "requirement_id": "Example artifacts | Where to find them"
EXAMPLES = {
    # === ACCESS CONTROL (AC) ===
    "3.1.1": {
        "a": "List of authorized users with roles/privileges | Active Directory user export, IAM console, HR onboarding records",
        "b": "List of processes/services acting on behalf of users with associated accounts | Service account inventory, system configuration docs, application architecture diagrams",
        "c": "List of authorized devices/systems with approval records | Device inventory spreadsheet, MDM console export, network access control (NAC) logs, CMDB export",
        "d": "Access control policy and account management procedures | Policy document (SSP Appendix), SOP for account provisioning/deprovisioning",
        "e": "Evidence of disabled/removed accounts for terminated employees | AD disabled accounts list, termination checklist with IT sign-off, ticket showing account removal within required timeframe",
    },
    "3.1.2": {
        "a": "Documentation defining authorized transactions/functions per user type | Role-based access matrix, access control policy, system security plan (SSP)",
        "b": "System configuration enforcing function-level access restrictions | Screenshots of role/group permissions in AD, application role configs, firewall rules limiting system functions",
    },
    "3.1.3": {
        "a": "Approved information flow authorizations | Data flow diagrams, SSP boundary descriptions, cross-domain transfer policies",
        "b": "Configuration of flow control mechanisms | Firewall rule sets, DLP policy screenshots, network segmentation diagrams, ACLs on routers/switches",
    },
    "3.1.4": {
        "a": "Documentation of separated duties | Separation of duties matrix, role definitions showing incompatible roles are split across personnel",
        "b": "System configuration enforcing separation | Screenshots showing no single user has conflicting roles (e.g., cannot both approve and execute), access reviews showing separation",
    },
    "3.1.5": {
        "a": "Least privilege policy and implementation evidence | Access control policy, screenshots of user permissions showing minimal necessary access, privileged account inventory",
        "b": "Evidence that privileged accounts are restricted to security functions only | Admin account audit, PAM tool configuration, logs showing admins use separate non-privileged accounts for daily work",
        "c": "Privileged account review records | Quarterly/annual access reviews with approvals, recertification records",
    },
    "3.1.6": {
        "a": "Evidence that non-privileged accounts are used for non-security functions | Policy requiring separate admin/user accounts, screenshots of admin users also having standard accounts, PAM session logs",
        "b": "Configuration preventing privileged accounts from non-security activities | GPO restricting admin accounts from email/web browsing, separate admin workstations or jump boxes",
    },
    "3.1.7": {
        "a": "Audit logs capturing privileged function execution | SIEM logs showing privileged operations, Windows Event logs (4672, 4673), sudo logs on Linux",
        "b": "Configuration preventing non-privileged users from executing privileged functions | UAC configuration, sudoers file, role-based permissions in applications",
    },
    "3.1.8": {
        "a": "Account lockout policy configuration | GPO showing lockout threshold and duration, screenshots of lockout settings in AD, application lockout configs",
        "b": "Evidence of lockout enforcement | Test results showing account locks after X failed attempts, incident logs of locked accounts",
    },
    "3.1.9": {
        "a": "System use notification/banner configuration | Screenshots of login banners on workstations, servers, network devices, VPN portals, and applications",
        "b": "Banner text meeting requirements | Documented banner language approved by legal/management, consistent with CUI handling requirements",
    },
    "3.1.10": {
        "a": "Session lock configuration | GPO showing screen lock timeout (typically 15 min), screensaver policy with password requirement",
        "b": "Pattern-hiding display evidence | Screenshot of lock screen showing no sensitive data visible, configuration of screen saver type",
    },
    "3.1.11": {
        "a": "Session termination configuration | GPO or application settings showing automatic session timeout/disconnect after inactivity period",
        "b": "Evidence of enforcement | Screenshots of timeout configs in RDP, VPN, web applications, SSH timeout settings",
    },
    "3.1.12": {
        "a": "Remote access monitoring tools and configuration | VPN logs, remote desktop gateway logs, SIEM alerts for remote sessions",
        "b": "Remote access control mechanisms | VPN configuration with MFA requirement, remote access policy, approved remote access methods list",
    },
    "3.1.13": {
        "a": "Cryptographic mechanisms for remote access | VPN configuration showing encryption (AES-256, TLS 1.2+), FIPS mode enabled on VPN appliance",
        "b": "Evidence of enforcement | Network capture showing encrypted tunnel, configuration screenshots of VPN/RDP crypto settings",
    },
    "3.1.14": {
        "a": "Managed access control points for remote access | Network diagram showing VPN concentrator/gateway as single entry point, firewall rules allowing remote access only through managed points",
        "b": "Configuration evidence | VPN gateway settings, firewall rules blocking direct remote access that bypasses the gateway",
    },
    "3.1.15": {
        "a": "Authorization records for remote privileged commands | Approval documentation, policy defining who can execute remote privileged commands",
        "b": "Monitoring/logging of remote privileged access | PAM tool logs, jump server session recordings, audit logs of remote admin sessions",
    },
    "3.1.16": {
        "a": "Wireless access authorization process | Wireless access policy, approval forms/tickets for wireless access",
        "b": "Wireless access restrictions | WLAN controller config showing SSID restrictions, 802.1X configuration, MAC filtering (if used), wireless usage policy",
    },
    "3.1.17": {
        "a": "Wireless authentication configuration | 802.1X/RADIUS config, WPA2/WPA3-Enterprise settings, certificate-based auth for wireless",
        "b": "Wireless encryption configuration | WLAN controller showing AES encryption, no WEP/WPA1, screenshots of wireless security settings",
    },
    "3.1.18": {
        "a": "Mobile device policy | MDM policy document, acceptable use policy for mobile devices",
        "b": "Mobile device management configuration | MDM console screenshots (Intune, JAMF, etc.) showing enrollment, restrictions, compliance policies",
        "c": "Mobile device inventory | MDM device list, enrolled devices with compliance status",
    },
    "3.1.19": {
        "a": "Mobile device encryption configuration | MDM policy enforcing full-device encryption, BitLocker/FileVault status on laptops, screenshots of encryption status",
        "b": "Verification of encryption enforcement | MDM compliance report showing encryption enabled on all enrolled devices",
    },
    "3.1.20": {
        "a": "Policy on external system connections | Interconnection security agreements (ISA), external system usage policy",
        "b": "Verification/control mechanisms | Firewall rules for partner connections, approved external system list, configuration of external access restrictions",
    },
    "3.1.21": {
        "a": "Policy limiting portable storage for CUI | Removable media policy, DLP configuration blocking unauthorized USB devices",
        "b": "Technical controls | GPO blocking USB storage, endpoint protection blocking removable media, approved device whitelist, DLP alerts for removable media",
    },
    "3.1.22": {
        "a": "Policy on publicly accessible system content | Content review procedures, web publishing approval workflow",
        "b": "Evidence of content review | Records of website/public content reviews, removal of CUI from public systems, content approval logs",
    },

    # === AWARENESS AND TRAINING (AT) ===
    "3.2.1": {
        "a": "Security awareness training records | LMS completion reports, training sign-in sheets, certificates of completion for all users",
        "b": "Training content/materials | Course slides or descriptions covering security risks, policies, CUI handling",
        "c": "Training schedule and policy | Annual training requirement in policy, new hire training within X days requirement",
    },
    "3.2.2": {
        "a": "Role-based training records for privileged users | Specialized training completion for admins, security personnel, developers",
        "b": "Training content for security roles | Admin-specific training materials, incident response training, secure coding training",
        "c": "Evidence of initial and refresher training | Training dates vs hire dates, annual refresher records",
    },
    "3.2.3": {
        "a": "Insider threat awareness training records | Training completion showing insider threat module, training content covering indicators",
        "b": "Training content | Insider threat awareness materials, reporting procedures for suspicious activity",
    },

    # === AUDIT AND ACCOUNTABILITY (AU) ===
    "3.3.1": {
        "a": "List of auditable events defined | Audit policy listing events to capture (logon/logoff, privilege use, object access, policy changes, etc.)",
        "b": "Audit configuration on systems | Windows Advanced Audit Policy screenshots, Linux auditd.conf, application audit settings, SIEM collection config",
        "c": "Sample audit logs | Exported event logs showing required events are captured, SIEM dashboard showing log collection",
    },
    "3.3.2": {
        "a": "Audit log content showing required fields | Sample logs with: what happened, when, where, source, outcome, user identity",
        "b": "Configuration ensuring required fields | Audit policy settings, log format configuration, SIEM parsing rules showing all required fields extracted",
    },
    "3.3.3": {
        "a": "Audit review procedures | Log review SOP, SIEM alert rules, scheduled review process documentation",
        "b": "Evidence of regular reviews | SIEM alert investigation records, weekly/monthly log review reports, ticketed anomalies from log reviews",
    },
    "3.3.4": {
        "a": "Alert/reporting mechanisms for audit failures | SIEM alerting on log collection failures, monitoring of disk space on log servers, email alerts for audit system errors",
        "b": "Evidence of alerts working | Sample alert for audit failure, incident ticket from audit system issue",
    },
    "3.3.5": {
        "a": "Audit log correlation capability | SIEM platform showing correlated events across systems, centralized log management architecture",
        "b": "Evidence of correlation | SIEM correlation rules, sample correlated incident showing events from multiple sources",
    },
    "3.3.6": {
        "a": "Audit log reduction/report generation capability | SIEM dashboards, log analysis tools, automated report generation",
        "b": "Sample reports | Automated audit summary reports, compliance dashboards, log analysis outputs",
    },
    "3.3.7": {
        "a": "Time synchronization configuration | NTP configuration on all systems (GPO for Windows, chrony/ntpd for Linux), network device NTP settings",
        "b": "Evidence of authoritative time source | NTP server configuration pointing to authoritative source (NIST, GPS, etc.), timestamp comparison across systems",
    },
    "3.3.8": {
        "a": "Audit log protection mechanisms | Log file permissions (read-only for non-admins), SIEM with write-once storage, log integrity monitoring",
        "b": "Audit log retention configuration | Retention policy, log archive configuration, evidence of logs retained for required period (typically 1+ years)",
    },
    "3.3.9": {
        "a": "Audit log management restricted to limited admins | Access control on SIEM/log servers, list of personnel with log management access",
        "b": "Protection against unauthorized modification | File integrity monitoring on logs, write-once media, separate log admin accounts",
    },

    # === CONFIGURATION MANAGEMENT (CM) ===
    "3.4.1": {
        "a": "System baseline configurations | Hardened build images, DISA STIG compliance scans, CIS Benchmark results, documented baseline for each system type",
        "b": "Baseline configuration documentation | Standard build documents, golden image specs, approved software lists",
        "c": "Evidence of baseline maintenance | Configuration scan results, change records showing baselines updated after changes",
    },
    "3.4.2": {
        "a": "Security configuration settings documentation | STIG/CIS settings applied, GPO exports, firewall rulesets, application hardening guides",
        "b": "Evidence of implementation | Compliance scan results (Nessus, SCAP), screenshots of security settings, configuration audit reports",
        "c": "Configuration monitoring | Regular scan results comparing current state to baseline, drift detection reports",
    },
    "3.4.3": {
        "a": "Change management process documentation | Change management policy/SOP, change advisory board (CAB) charter",
        "b": "Change request records | Sample change tickets with approval, implementation, and verification steps documented",
        "c": "Security impact analysis records | Change requests showing security review/approval before implementation",
    },
    "3.4.4": "Security impact analysis of changes | Change management records showing security impact assessment before implementation, risk assessment of proposed changes | Change management system (ServiceNow, Jira), CAB meeting minutes",
    "3.4.5": {
        "a": "Physical access restrictions to systems | Server room access logs, data center badge reader logs, locked wiring closets",
        "b": "Logical access restrictions | Firewall rules, network ACLs, jump server requirements, VPN-only access to management interfaces",
        "c": "Configuration change restrictions | Change management approval workflow, restricted admin accounts, configuration management tool access controls",
    },
    "3.4.6": {
        "a": "Least functionality policy | Application whitelisting policy, unnecessary services disabled, ports/protocols restricted",
        "b": "Evidence of implementation | Application whitelist configuration (AppLocker, SRP), disabled services list, Nessus scan showing minimal open ports, firewall deny-all with explicit allows",
    },
    "3.4.7": {
        "a": "Restrictions on non-essential programs/functions | Software restriction policies, blocked application categories, browser extension controls",
        "b": "Usage monitoring | Application usage logs, unauthorized software detection scans, DLP monitoring for unauthorized tools",
    },
    "3.4.8": {
        "a": "Application execution policy (whitelisting/blacklisting) | AppLocker or WDAC policy exports, application control configuration",
        "b": "Evidence of enforcement | Blocked application logs, compliance scan showing only approved software running",
    },
    "3.4.9": {
        "a": "User-installed software policy | Policy document restricting software installation, GPO removing local admin rights",
        "b": "Technical enforcement | UAC configuration, software installation restrictions, SCCM/Intune software deployment as sole method",
    },

    # === IDENTIFICATION AND AUTHENTICATION (IA) ===
    "3.5.1": {
        "a": "User identification procedures | Account provisioning SOP, unique username policy, identity proofing procedures",
        "b": "System identification evidence | Unique device identifiers, certificate-based machine authentication, device naming standards",
        "c": "User authentication mechanisms | AD authentication configuration, MFA deployment evidence, password policy GPO",
    },
    "3.5.2": {
        "a": "Authentication mechanisms for network access | AD/LDAP authentication for all systems, 802.1X for network access, VPN authentication config",
        "b": "Device authentication | Machine certificates, NAC configuration requiring device authentication, trusted device policies",
    },
    "3.5.3": {
        "a": "Multi-factor authentication for privileged accounts | MFA configuration for admin accounts (Azure MFA, Duo, RSA), conditional access policies requiring MFA for admin roles",
        "b": "Multi-factor authentication for network access | MFA on VPN, MFA for remote desktop, MFA for cloud admin portals, conditional access policies",
    },
    "3.5.4": "Replay-resistant authentication | Kerberos configuration (no NTLM), TLS certificate-based auth, FIDO2/WebAuthn deployment, PKI infrastructure documentation | AD authentication settings, network authentication configs",
    "3.5.5": {
        "a": "Identifier management procedures | Account naming conventions, unique ID policy, procedures for disabling identifiers after inactivity",
        "b": "Identifier reuse prevention | Policy prohibiting reuse of user IDs, AD configuration for unique identifiers",
    },
    "3.5.6": {
        "a": "Authenticator management procedures | Password policy (complexity, length, history), certificate lifecycle management, token provisioning SOP",
        "b": "Initial authenticator distribution | Secure password delivery method, initial token enrollment process",
        "c": "Authenticator change/refresh procedures | Password expiration settings, certificate renewal process, compromised credential response",
    },
    "3.5.7": {
        "a": "Password complexity enforcement | AD password policy GPO (min length, complexity, history), application password requirements",
        "b": "Password storage protections | Hashed/salted password storage verification, no plaintext passwords, encrypted password databases",
    },
    "3.5.8": {
        "a": "Obscured password feedback | Login screens showing dots/asterisks for password entry (screenshots of all login interfaces)",
        "b": "All systems verified | Screenshots from workstations, servers, VPN portal, web applications, network devices showing masked password fields",
    },
    "3.5.9": "Temporary password change requirement | AD setting requiring password change at first logon, application configuration forcing temporary password change | GPO settings, application auth configuration screenshots",
    "3.5.10": {
        "a": "Cryptographic protection of passwords in storage | AD using AES-256 for Kerberos, no LM hashes stored, application password hashing (bcrypt/scrypt/argon2)",
        "b": "Cryptographic protection of passwords in transit | TLS 1.2+ for all authentication traffic, LDAPS configuration, encrypted admin protocols (SSH not Telnet)",
    },
    "3.5.11": "Obscured authentication feedback | Screenshots of all login prompts showing masked/hidden password entry, no systems displaying passwords in cleartext | Login screen screenshots from every system type",

    # === INCIDENT RESPONSE (IR) ===
    "3.6.1": {
        "a": "Incident response plan | IR plan document covering: preparation, detection, analysis, containment, eradication, recovery, post-incident activities",
        "b": "Incident response roles and responsibilities | IR team roster with roles, contact information, escalation procedures",
        "c": "IR plan review/update records | Dated plan versions showing annual review, lessons learned incorporated from incidents",
    },
    "3.6.2": {
        "a": "Incident tracking and documentation | Incident ticket system (ServiceNow, Jira), IR log templates, sample completed incident reports",
        "b": "Incident reporting procedures | Reporting requirements to management, external reporting requirements (DIBNet, law enforcement), reporting timelines",
    },
    "3.6.3": "Incident response testing records | Tabletop exercise records, IR drill after-action reports, red team/penetration test results triggering IR process | Annual tabletop exercise documentation, exercise participant sign-in sheets",

    # === MAINTENANCE (MA) ===
    "3.7.1": "System maintenance records | Maintenance logs, patch management reports, scheduled maintenance calendar, maintenance tickets | WSUS/SCCM reports, ticketing system, vendor maintenance records",
    "3.7.2": {
        "a": "Maintenance tool controls | Approved maintenance tool list, tool inspection records, sanitization of tools before/after use",
        "b": "Media containing diagnostic programs | Integrity verification of maintenance media, approved diagnostic software list",
    },
    "3.7.3": "Off-site maintenance equipment sanitization | Sanitization procedures for equipment leaving facility, data wipe verification records, chain of custody forms | Equipment checkout log, sanitization certificates",
    "3.7.4": "Diagnostic media malware checks | Scan records for maintenance media before use, approved/clean media library, boot media integrity verification | Antivirus scan logs, media verification records",
    "3.7.5": {
        "a": "Non-local maintenance authorization | Remote maintenance policy, VPN/remote access approval for maintenance, authorized remote maintenance personnel list",
        "b": "Non-local maintenance monitoring | Session recording of remote maintenance, audit logs of remote maintenance sessions, maintenance session approval tickets",
    },
    "3.7.6": "Maintenance personnel supervision | Escort procedures for maintenance personnel without clearance, supervision logs, visitor maintenance logs | Visitor logs, escort assignment records, maintenance work orders with supervision noted",

    # === MEDIA PROTECTION (MP) ===
    "3.8.1": {
        "a": "Media protection policy | Policy covering CUI media handling, marking, storage, transport, sanitization, destruction",
        "b": "Media access controls | Physical media storage (locked cabinets/safes), logical access to digital media (encrypted drives), media checkout/check-in logs",
    },
    "3.8.2": "Media access limited to authorized users | Media access control list, locked storage access logs, digital media permission settings | Physical access logs for media storage, file share permissions for digital media",
    "3.8.3": {
        "a": "Media sanitization procedures | Sanitization SOP per media type (wipe, degauss, destroy), NIST SP 800-88 compliance",
        "b": "Sanitization records | Certificates of destruction, wipe verification logs, degaussing records, shredding vendor certificates",
        "c": "Sanitization tools | Approved sanitization software (DBAN, Blancco), verified degaussers, physical destruction equipment",
    },
    "3.8.4": {
        "a": "CUI media marking | Samples of marked media (CUI banners on documents, labeled drives/tapes), marking procedures",
        "b": "Marking exemptions documented | List of media exempt from marking with justification",
    },
    "3.8.5": {
        "a": "Media transport protections | Encrypted transport containers, courier procedures, tracked shipping for CUI media",
        "b": "Custodian/accountability during transport | Chain of custody forms, transport logs, designated transport personnel",
    },
    "3.8.6": "CUI media confidentiality during transport | Encryption of portable media (BitLocker To Go, VeraCrypt), locked transport containers, tamper-evident packaging | Encrypted drive configuration screenshots, transport procedure documentation",
    "3.8.7": "Removable media usage controls | USB device control policy (GPO, endpoint protection), DLP for removable media, approved device whitelist | GPO blocking USB, endpoint protection console showing device control rules",
    "3.8.8": "Portable storage prohibition where no owner | Policy prohibiting unidentifiable portable storage devices, procedures for found media, employee awareness of prohibition | Policy document, awareness training covering this topic",
    "3.8.9": "Backup CUI confidentiality protection | Encrypted backup configuration, backup media stored in access-controlled location, backup encryption keys managed separately | Backup software encryption settings, backup storage access logs",

    # === PERSONNEL SECURITY (PS) ===
    "3.9.1": "Personnel screening records | Background check completion records, screening criteria documentation, rescreening schedule | HR records (redacted), background check vendor reports, screening policy",
    "3.9.2": {
        "a": "CUI protection during personnel actions | Termination checklist (account disable, badge return, CUI return), transfer procedures (access review/modification)",
        "b": "System access revocation evidence | Ticket/record showing account disabled within required timeframe of termination, badge deactivation logs, exit interview records",
    },

    # === PHYSICAL PROTECTION (PE) ===
    "3.10.1": {
        "a": "Physical access authorizations | Authorized access list for facilities/server rooms, badge issuance records, access approval forms",
        "b": "Physical access controls | Badge reader configurations, security guard procedures, key/combination management for restricted areas",
    },
    "3.10.2": {
        "a": "Physical access monitoring | CCTV/surveillance system configuration, guard tour records, badge reader log reviews",
        "b": "Physical access logs | Badge swipe reports, visitor sign-in sheets, server room access logs, CCTV footage retention evidence",
    },
    "3.10.3": {
        "a": "Visitor procedures | Visitor policy, sign-in/sign-out procedures, escort requirements",
        "b": "Visitor records | Visitor log samples, badge issuance for visitors, escort assignment records",
        "c": "Visitor area restrictions | Documented restricted areas, visitor badge distinguishing from employee badges",
    },
    "3.10.4": "Physical access audit logs maintained | Badge reader reports, visitor logs, server room access logs retained for required period | Physical access control system exports, archived visitor logs",
    "3.10.5": {
        "a": "Physical access control devices | Badge reader inventory, key management log, cipher lock inventory, biometric scanner configuration",
        "b": "Physical barrier protections | Fence/wall documentation, mantrap configuration, anti-tailgating measures, camera coverage maps",
    },
    "3.10.6": {
        "a": "Alternate work site policy | Telework/remote work policy addressing CUI handling, home office security requirements",
        "b": "Alternate work site security controls | VPN requirement, encrypted laptop requirement, clean desk policy for remote workers, visitor restrictions at home offices",
    },

    # === RISK ASSESSMENT (RA) ===
    "3.11.1": {
        "a": "Risk assessment documentation | Current risk assessment report, risk register, threat analysis",
        "b": "Risk assessment methodology | Risk assessment procedures, frequency of assessments, tools used (NIST CSF, FAIR, etc.)",
        "c": "Risk assessment review/update | Dated assessment versions, annual review records, updates after significant changes",
    },
    "3.11.2": {
        "a": "Vulnerability scanning procedures and results | Nessus/Qualys/OpenVAS scan reports, scanning schedule, scan coverage (all CUI systems)",
        "b": "Vulnerability remediation evidence | Patch management reports, vulnerability remediation tickets, risk acceptance documentation for unpatched vulns",
        "c": "Scanning frequency | Scan schedule documentation, automated recurring scan configuration",
    },
    "3.11.3": {
        "a": "Vulnerability remediation plan | Remediation timelines by severity (critical/high/medium/low), remediation tracking in ticketing system",
        "b": "Remediation evidence | Before/after scan comparisons, patch deployment records, configuration change records addressing vulnerabilities",
    },

    # === SECURITY ASSESSMENT (CA) ===
    "3.12.1": {
        "a": "Security control assessment plan | Assessment scope, methodology, schedule, assessor qualifications",
        "b": "Assessment results | Assessment report with findings, risk ratings, recommendations",
        "c": "Evidence of periodic assessments | Annual assessment reports, continuous monitoring data",
    },
    "3.12.2": {
        "a": "Plan of Action and Milestones (POA&M) | Current POA&M document listing known deficiencies, remediation plans, milestones, responsible parties, completion dates",
        "b": "POA&M updates | Evidence of regular POA&M reviews and updates, closed items with verification",
    },
    "3.12.3": "Continuous monitoring of security controls | SIEM dashboards, automated compliance scanning (scheduled), continuous monitoring plan/strategy | SIEM console, compliance tool reports, monitoring procedures document",
    "3.12.4": {
        "a": "System security plan (SSP) | Current SSP document describing system boundary, environment, security controls implementation",
        "b": "SSP review and update records | Dated versions showing updates, annual review records, updates after significant system changes",
    },

    # === SYSTEM AND COMMUNICATIONS PROTECTION (SC) ===
    "3.13.1": {
        "a": "Boundary protection mechanisms | Firewall configurations at external boundaries, IDS/IPS deployment, DMZ architecture",
        "b": "Network architecture documentation | Network diagrams showing boundaries, data flow diagrams for CUI, boundary device inventory",
        "c": "Monitoring at boundaries | IDS/IPS alerts, firewall log reviews, NetFlow analysis, boundary traffic monitoring dashboards",
        "d": "Internal boundary protections | Internal firewalls, VLAN segmentation, network segmentation between CUI and non-CUI systems",
        "e": "Key internal boundary protections | Segmentation between user networks and server networks, DMZ configurations, microsegmentation policies",
        "f": "Communications monitoring configuration | IDS/IPS rules, DLP at network boundaries, email gateway filtering, proxy configurations",
        "g": "Boundary device configurations | Firewall rulesets with deny-by-default, router ACLs, proxy allow/block lists",
        "h": "Exception documentation | Documented exceptions to boundary policies with risk acceptance, temporary rule approvals",
    },
    "3.13.2": {
        "a": "Security architecture documentation | System architecture documents incorporating security principles, defense-in-depth strategy",
        "b": "Secure development practices | SDLC documentation including security requirements, secure coding standards, code review procedures",
        "c": "Network segmentation design | Network diagrams showing segmented architecture, VLAN assignments, firewall zones",
        "d": "Security engineering principles applied | Design documents referencing least privilege, defense in depth, fail-safe defaults",
        "e": "Evidence of implementation | Configuration screenshots showing layered security, penetration test results validating architecture",
        "f": "Architecture review records | Periodic architecture review meeting notes, updates to architecture based on threat changes",
    },
    "3.13.3": {
        "a": "User functionality vs management functionality separation | Separate management interfaces, admin networks segregated from user networks, out-of-band management",
        "b": "Implementation evidence | Network diagrams showing management VLAN, jump server architecture, management interface ACLs",
        "c": "Physical or logical separation | Separate management workstations, dedicated management network, virtualization isolation between functions",
    },
    "3.13.4": "Shared resource information transfer prevention | Configuration preventing covert channel exploitation, process isolation settings, memory protection configuration | Virtualization isolation settings, OS hardening configurations, shared resource access controls",
    "3.13.5": {
        "a": "Public-facing system segmentation | DMZ architecture, separate network segments for public-facing systems, firewall rules isolating public systems from internal CUI systems",
        "b": "Implementation evidence | Network diagrams, firewall rules showing isolation, VLAN configurations for public-facing vs internal systems",
    },
    "3.13.6": {
        "a": "Default-deny network policy | Firewall configurations with deny-all default rule, explicit allow rules documented and justified",
        "b": "Evidence of deny-by-default | Firewall rule exports showing default deny, network traffic blocked by default with exceptions, ACL configurations",
    },
    "3.13.7": "Split tunneling prevention | VPN configuration forcing all traffic through VPN tunnel (no split tunneling), GPO preventing local network access while on VPN | VPN client configuration screenshots, VPN server settings, GPO for tunnel configuration",
    "3.13.8": {
        "a": "CUI transmission encryption | TLS 1.2+ configuration for all CUI data in transit, email encryption (S/MIME, TLS), HTTPS enforcement",
        "b": "Cryptographic implementation evidence | Certificate inventory, TLS configuration scans (SSL Labs), email gateway encryption settings",
        "c": "Alternative physical safeguards (if applicable) | Protected distribution system documentation, secured wiring, TEMPEST measures",
    },
    "3.13.9": {
        "a": "Network session termination configuration | Firewall session timeout settings, VPN idle timeout, application session timeout",
        "b": "Evidence of session termination | Configuration screenshots showing timeout values, tested/verified session disconnects",
        "c": "Inactivity timeout settings | Per-system timeout configurations, policy defining acceptable timeout periods",
    },
    "3.13.10": {
        "a": "Cryptographic key management procedures | Key generation, distribution, storage, rotation, revocation, destruction procedures",
        "b": "Key management implementation | Certificate authority configuration, key escrow/recovery procedures, key rotation evidence, HSM configuration (if used)",
    },
    "3.13.11": "FIPS-validated cryptography for CUI confidentiality | FIPS 140-2/3 validated module certificates, system FIPS mode configuration (Windows FIPS policy, Linux FIPS mode), VPN FIPS configuration | FIPS validation certificate numbers, GPO FIPS settings, crypto module documentation",
    "3.13.12": {
        "a": "Collaborative computing device policy | Policy on webcams, microphones, smart speakers in CUI areas, allowed/prohibited device list",
        "b": "Remote activation prevention | Camera/microphone disable mechanisms, hardware covers/switches, software controls preventing remote activation",
        "c": "User indication of active devices | Indicator lights, software notifications when camera/mic active, physical lens covers",
    },
    "3.13.13": {
        "a": "Mobile code policy | Policy defining allowed/blocked mobile code (Java, JavaScript, ActiveX, Flash, macros), risk categories",
        "b": "Mobile code controls | Browser security settings, email attachment filtering, macro policies in Office (GPO), application whitelisting blocking unauthorized mobile code",
    },
    "3.13.14": {
        "a": "VoIP security controls | VoIP network segmentation, encrypted voice traffic (SRTP/TLS), VoIP firewall rules",
        "b": "VoIP monitoring | Call logging, VoIP traffic monitoring, QoS/security monitoring dashboards",
    },
    "3.13.15": "Session authenticity protection | TLS for all sessions handling CUI, mutual authentication configuration, certificate validation, session token protection | TLS configuration on web servers/applications, certificate deployment evidence",
    "3.13.16": "CUI at-rest encryption | Full disk encryption (BitLocker, FileVault, LUKS), database encryption (TDE), file-level encryption for CUI stores, encrypted backups | BitLocker status reports, encryption compliance dashboards, database TDE configuration",

    # === SYSTEM AND INFORMATION INTEGRITY (SI) ===
    "3.14.1": {
        "a": "Flaw identification process | Vulnerability management program documentation, patch management policy, vendor advisory monitoring",
        "b": "Flaw remediation evidence | Patch deployment reports, vulnerability scan before/after remediation, WSUS/SCCM compliance reports",
        "c": "Patch management timeline | Remediation SLAs by severity, evidence of meeting timelines, exception/risk acceptance for delayed patches",
    },
    "3.14.2": {
        "a": "Malicious code protection deployment | Antivirus/EDR on all systems, email gateway antimalware, web proxy malware scanning",
        "b": "Malicious code protection configuration | AV/EDR policy settings, real-time scanning enabled, scheduled full scans, quarantine procedures",
        "c": "Signature/definition update evidence | AV update status across all endpoints, automatic update configuration, update compliance reports",
    },
    "3.14.3": {
        "a": "Security alert monitoring | Subscriptions to CISA alerts, vendor security bulletins, threat intelligence feeds",
        "b": "Advisory response process | Procedures for evaluating and responding to security advisories, records of advisory reviews and actions taken",
    },
    "3.14.4": "Malware protection mechanism updates | AV/EDR auto-update configuration, update deployment logs, signature currency reports across all endpoints | AV console showing update status, WSUS/SCCM definition update reports",
    "3.14.5": {
        "a": "Periodic system scans | Scheduled antimalware scan configuration, scan completion reports, full system scan evidence",
        "b": "Real-time scanning | AV/EDR real-time protection enabled on all endpoints, on-access scanning configuration",
        "c": "Scan on external media/download | Configuration scanning removable media on insertion, download scanning in browsers/email, sandbox configuration",
    },
    "3.14.6": {
        "a": "Inbound communications monitoring | Email gateway logs, web proxy logs, IDS/IPS for inbound traffic, firewall inbound traffic analysis",
        "b": "Internal system monitoring | SIEM alerts for internal anomalies, endpoint detection alerts, user behavior analytics (UBA)",
        "c": "Outbound communications monitoring | DLP monitoring outbound traffic, proxy logs for data exfiltration, DNS monitoring, outbound firewall rules with logging",
    },
    "3.14.7": {
        "a": "Authorized system use defined | Acceptable use policy, system use banners defining authorized use, baseline of normal activity",
        "b": "Unauthorized use identification | SIEM rules detecting anomalous behavior, failed access attempt monitoring, after-hours access alerts, unauthorized software detection",
    },
}


def seed_examples():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # Ensure column exists
    try:
        conn.execute("SELECT example_artifacts FROM objectives LIMIT 1")
    except Exception:
        conn.execute("ALTER TABLE objectives ADD COLUMN example_artifacts TEXT DEFAULT ''")
        conn.commit()

    # Get all objectives
    objectives = conn.execute("SELECT id, requirement_id FROM objectives ORDER BY sort_as").fetchall()

    updated = 0
    for obj in objectives:
        obj_id = obj["id"]
        req_id = obj["requirement_id"]

        # Extract bracket letter if present (e.g., "3.1.1[a]" -> "a")
        bracket_key = None
        if "[" in obj_id:
            bracket_key = obj_id.split("[")[1].rstrip("] \t")

        examples = EXAMPLES.get(req_id)
        if examples is None:
            continue

        if isinstance(examples, str):
            # Single objective requirement
            text = examples
        elif isinstance(examples, dict) and bracket_key:
            text = examples.get(bracket_key, "")
        elif isinstance(examples, dict) and not bracket_key:
            # Single-objective req with dict (shouldn't happen but fallback)
            text = " | ".join(examples.values())
        else:
            text = ""

        if text:
            conn.execute("UPDATE objectives SET example_artifacts = ? WHERE id = ?", (text, obj_id))
            updated += 1

    conn.commit()
    conn.close()
    print(f"Seeded example artifacts for {updated} objectives")


if __name__ == "__main__":
    seed_examples()
