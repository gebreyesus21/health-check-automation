"""
ServiceNow integration for automatic ticket creation.
"""

import requests
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from alerters.base import BaseAlerter
from checks.base import CheckResult, Status, Severity
from utils.logger import setup_logger
from config.settings import settings

class ServiceNowIntegration(BaseAlerter):
    """
    Create and update ServiceNow incidents for critical failures.
    """
    
    def __init__(self):
        self.logger = setup_logger("servicenow")
        self.instance = settings.SERVICENOW_INSTANCE
        self.username = settings.SERVICENOW_USERNAME
        self.password = settings.SERVICENOW_PASSWORD
        self.enabled = settings.SERVICENOW_ENABLED
        
        # Track open incidents to avoid duplicates
        self.open_incidents: Dict[str, str] = {}  # fingerprint -> incident_id
        
        if self.enabled and not self.instance:
            self.logger.warning("ServiceNow enabled but instance not configured")
            self.enabled = False
    
    def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Optional[Dict]:
        """Make authenticated request to ServiceNow API."""
        if not self.enabled:
            return None
        
        url = f"https://{self.instance}.service-now.com/api/now{endpoint}"
        
        auth = (self.username, self.password)
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        
        try:
            if method == "GET":
                response = requests.get(url, auth=auth, headers=headers, timeout=30)
            elif method == "POST":
                response = requests.post(url, auth=auth, headers=headers, json=data, timeout=30)
            elif method == "PUT":
                response = requests.put(url, auth=auth, headers=headers, json=data, timeout=30)
            else:
                return None
            
            response.raise_for_status()
            return response.json().get("result", {})
            
        except Exception as e:
            self.logger.error(f"ServiceNow API error: {e}")
            return None
    
    def _generate_fingerprint(self, result: CheckResult) -> str:
        """Generate unique fingerprint for incident deduplication."""
        return f"{result.check_name}:{result.target}:{result.severity.value}"
    
    def _find_existing_incident(self, fingerprint: str) -> Optional[str]:
        """Check if there's an open incident for this issue."""
        if fingerprint in self.open_incidents:
            return self.open_incidents[fingerprint]
        
        # Search in ServiceNow
        query = f"short_descriptionLIKE{fingerprint}&stateIN=1,2"  # New, In Progress
        response = self._make_request("GET", f"/table/incident?{query}")
        
        if response and isinstance(response, list) and len(response) > 0:
            incident_id = response[0].get("sys_id")
            self.open_incidents[fingerprint] = incident_id
            return incident_id
        
        return None
    
    def send(self, result: CheckResult) -> bool:
        """
        Create or update ServiceNow incident for critical failures.
        """
        if not self.enabled:
            return False
        
        # Only create incidents for critical failures
        if result.severity != Severity.CRITICAL or result.status == Status.PASS:
            return True
        
        fingerprint = self._generate_fingerprint(result)
        
        # Check if incident already exists
        existing_incident = self._find_existing_incident(fingerprint)
        
        if existing_incident:
            # Update existing incident
            return self._update_incident(existing_incident, result)
        else:
            # Create new incident
            return self._create_incident(result, fingerprint)
    
    def _create_incident(self, result: CheckResult, fingerprint: str) -> bool:
        """Create a new ServiceNow incident."""
        
        # Build incident description
        description = f"""
## Health Check Failure Alert

**Check:** {result.check_name}
**Target:** {result.target}
**Status:** {result.status.value.upper()}
**Severity:** {result.severity.value.upper()}

## Details
{result.message}

## Metrics
```json
{self._format_json(result.details)}