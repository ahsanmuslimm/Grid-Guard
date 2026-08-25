"""
GridGuard — NVD CVE Lookup Tool
Queries the NIST National Vulnerability Database API v2.0.
Returns real CVE IDs with CVSS scores for SCADA/ICS attack types.
All lookups traced to Arize Phoenix with hallucination-detectable output attributes.
Register for a free API key at: https://nvd.nist.gov/developers/request-an-api-key
"""

import time
import requests
from typing import Any
from opentelemetry import trace
from tools.secrets import get_secret_optional

_tracer = trace.get_tracer("gridguard.cve_lookup")

NVD_BASE_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"

# NVD keywordSearch matches all supplied terms closely. Use short progressive
# queries instead of one over-constrained multi-keyword expression.
ATTACK_TYPE_KEYWORDS: dict[str, list[str]] = {
    "ransomware": ["SCADA remote code execution", "industrial control remote code execution", "Siemens SIMATIC"],
    "unauthorized_access": ["SCADA authentication", "industrial control authentication", "SCADA access control"],
    "ddos": ["SCADA denial of service", "industrial control denial of service", "Siemens denial of service"],
    "data_exfiltration": ["SCADA information disclosure", "industrial control information disclosure", "SCADA read access"],
}

# Curated fallback CVEs when the NVD API is unavailable or rate-limited
FALLBACK_CVES: dict[str, list[dict]] = {
    "ransomware": [
        {
            "id": "CVE-2023-28489",
            "description": "Siemens CP-8031/CP-8050 command injection can allow unauthenticated remote code execution when Remote Operation is enabled.",
            "cvss_score": 9.8,
            "severity": "CRITICAL"
        }
    ],
    "unauthorized_access": [
        {
            "id": "CVE-2022-2513",
            "description": "Hitachi Energy PCM600 stores IED credentials in cleartext database and log files, enabling unauthorized device changes.",
            "cvss_score": 7.1,
            "severity": "HIGH"
        }
    ],
    "ddos": [
        {
            "id": "CVE-2023-1256",
            "description": "AVEVA Plant SCADA and Telemetry Server improper authorization can allow remote denial of service and alarm-state tampering.",
            "cvss_score": 9.8,
            "severity": "CRITICAL"
        }
    ],
    "data_exfiltration": [
        {
            "id": "CVE-2023-1256",
            "description": "AVEVA Plant SCADA and Telemetry Server improper authorization can allow unauthenticated remote reading of process data.",
            "cvss_score": 9.8,
            "severity": "CRITICAL"
        }
    ]
}


def lookup_cve(attack_type: str, affected_system: str = "SCADA") -> dict[str, Any]:
    """
    Search the NIST NVD for CVEs matching the detected attack type.

    Args:
        attack_type: One of 'ransomware', 'unauthorized_access', 'ddos', 'data_exfiltration'
        affected_system: Target system context, default 'SCADA'

    Returns:
        Dict with CVE list (id, description, cvss_score, severity), total found, and source.
    """
    with _tracer.start_as_current_span("investigation.cve_lookup") as span:
        keyword_queries = ATTACK_TYPE_KEYWORDS.get(
            attack_type.lower(),
            [f"{affected_system} {attack_type}"],
        )

        span.set_attribute("cve.attack_type", attack_type)
        span.set_attribute("cve.affected_system", affected_system)
        span.set_attribute("cve.keywords", str(keyword_queries))
        span.set_attribute("input.value", f"attack_type={attack_type}, system={affected_system}")

        headers: dict[str, str] = {}
        nvd_key = get_secret_optional("NVD_API_KEY")
        if nvd_key:
            headers["apiKey"] = nvd_key
        else:
            time.sleep(0.6)

        try:
            queries_to_try = keyword_queries if nvd_key else keyword_queries[:1]
            for keywords in queries_to_try:
                response = requests.get(
                    NVD_BASE_URL,
                    params={"keywordSearch": keywords, "resultsPerPage": 5, "startIndex": 0},
                    headers=headers,
                    timeout=15,
                )
                response.raise_for_status()
                data = response.json()
                vulnerabilities = data.get("vulnerabilities", [])
                cves = []

                for vuln in vulnerabilities:
                    cve_obj = vuln.get("cve", {})
                    descriptions = cve_obj.get("descriptions", [])
                    description = next(
                        (d["value"] for d in descriptions if d.get("lang") == "en"),
                        "No description available",
                    )
                    metrics = cve_obj.get("metrics", {})
                    cvss_score = None
                    severity = "UNKNOWN"
                    for cvss_key in ["cvssMetricV31", "cvssMetricV30", "cvssMetricV2"]:
                        metric_list = metrics.get(cvss_key, [])
                        if metric_list:
                            cvss_data = metric_list[0].get("cvssData", {})
                            cvss_score = cvss_data.get("baseScore")
                            severity = cvss_data.get("baseSeverity", "UNKNOWN")
                            break
                    cves.append({
                        "id": cve_obj.get("id", ""),
                        "description": description[:200],
                        "cvss_score": cvss_score,
                        "severity": severity,
                    })

                if cves:
                    cve_ids = [c["id"] for c in cves]
                    span.set_attribute("cve.source", "nvd_live")
                    span.set_attribute("cve.count", len(cves))
                    span.set_attribute("cve.ids_found", str(cve_ids))
                    span.set_attribute("cve.successful_query", keywords)
                    span.set_attribute("output.value", str(cve_ids))

                    return {
                        "cves": cves,
                        "total_found": data.get("totalResults", len(cves)),
                        "attack_type": attack_type,
                        "source": "nvd_live",
                        "keywords_used": keywords,
                        "queries_tried": queries_to_try[: queries_to_try.index(keywords) + 1],
                    }

        except requests.exceptions.Timeout:
            span.set_attribute("cve.error", "timeout")
        except requests.exceptions.HTTPError as e:
            span.set_attribute("cve.error", f"http_{e.response.status_code}")
        except Exception as e:
            span.set_attribute("cve.error", str(e)[:100])

        # Fallback
        fallback = FALLBACK_CVES.get(attack_type.lower(), [])
        fallback_ids = [c["id"] for c in fallback]
        span.set_attribute("cve.source", "nvd_fallback")
        span.set_attribute("cve.count", len(fallback))
        span.set_attribute("cve.ids_found", str(fallback_ids))
        span.set_attribute("output.value", str(fallback_ids))

        return {
            "cves": fallback,
            "total_found": len(fallback),
            "attack_type": attack_type,
            "source": "nvd_fallback",
            "keywords_used": keyword_queries[0],
            "queries_tried": keyword_queries if nvd_key else keyword_queries[:1],
        }
