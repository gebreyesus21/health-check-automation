"""
PRTG integration for pushing health check results to existing monitoring system.
"""

import requests
from typing import Dict, Any, List
from urllib.parse import quote

from alerters.base import BaseAlerter
from checks.base import CheckResult, Status, Severity
from utils.logger import setup_logger
from config.settings import settings

class PRTGIntegration(BaseAlerter):
    """
    Push health check results to PRTG via custom sensors.
    """
    
    def __init__(self):
        self.logger = setup_logger("prtg_integration")
        self.server = settings.PRTG_SERVER
        self.username = settings.PRTG_USERNAME
        self.password = settings.PRTG_PASSWORD
        self.enabled = settings.PRTG_ENABLED
        
        if self.enabled and not self.server:
            self.logger.warning("PRTG integration enabled but server not configured")
            self.enabled = False
    
    def _make_request(self, params: Dict[str, Any]) -> bool:
        """Make authenticated request to PRTG API."""
        if not self.enabled:
            return False
        
        url = f"{self.server}/api/table.json"
        
        # Add authentication
        params.update({
            "username": self.username,
            "password": self.password,
        })
        
        try:
            response = requests.get(
                url,
                params=params,
                timeout=10,
                verify=False,  # For internal networks
            )
            response.raise_for_status()
            return True
        except Exception as e:
            self.logger.error(f"Failed to push to PRTG: {e}")
            return False
    
    def send(self, result: CheckResult) -> bool:
        """
        Push individual check result to PRTG as a custom sensor value.
        """
        if not self.enabled:
            return False
        
        # Map severity to PRTG sensor status
        status_map = {
            Status.PASS: 0,      # OK
            Status.WARN: 1,      # Warning
            Status.FAIL: 2,      # Down
            Status.ERROR: 3,     # Unknown
        }
        
        sensor_status = status_map.get(result.status, 3)
        
        # Format sensor name from check and target
        sensor_name = f"{result.check_name}_{result.target.replace('.', '_')}"
        
        params = {
            "content": "custom_sensor",
            "name": sensor_name,
            "value": sensor_status,
            "message": result.message[:255],  # PRTG message limit
        }
        
        # Add numeric value if available
        if result.details and "value" in result.details:
            params["value"] = float(result.details["value"])
        
        return self._make_request(params)
    
    def send_batch(self, results: List[CheckResult]) -> Dict[str, int]:
        """
        Push batch of results to PRTG.
        """
        if not self.enabled:
            return {"sent": 0, "failed": 0}
        
        sent = 0
        failed = 0
        
        for result in results:
            if self.send(result):
                sent += 1
            else:
                failed += 1
        
        return {"sent": sent, "failed": failed}
    
    def create_prtg_sensor(self, host: str, check_name: str, check_type: str) -> bool:
        """
        Create a custom sensor in PRTG for a new check.
        """
        if not self.enabled:
            return False
        
        # Get device ID for the host
        device_params = {
            "content": "devices",
            "filter_name": host,
        }
        
        response = requests.get(
            f"{self.server}/api/table.json",
            params=device_params,
            auth=(self.username, self.password),
            timeout=10,
            verify=False,
        )
        
        if response.status_code != 200:
            self.logger.error(f"Failed to get device for {host}")
            return False
        
        devices = response.json().get("devices", [])
        if not devices:
            self.logger.warning(f"No device found for host {host}")
            return False
        
        device_id = devices[0].get("objid")
        
        # Create custom sensor
        sensor_params = {
            "content": "addsensor",
            "name": f"Health Check - {check_name}",
            "deviceid": device_id,
            "sensor_type": "exe/custom",
            "params": {
                "exefile": "health_check.py",
                "params": f"--check {check_name} --target {host}",
            },
        }
        
        return self._make_request(sensor_params)