"""
Health checks for telecom OSS applications (NetEco, iMaster, MAE, ElasticNet, etc.)
"""

import requests
import json
from typing import Dict, Any, Optional
from urllib3.exceptions import InsecureRequestWarning

# Disable SSL warnings for internal networks
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

from checks.base import BaseCheck, CheckResult, Status, Severity
from inventory.models import InfrastructureNode, PlatformType

class ApplicationHealthCheck(BaseCheck):
    """
    Health check for OSS applications with platform-specific endpoints.
    """
    
    def __init__(self, name: str = "application_health", timeout: int = 30):
        super().__init__(name, timeout)
        
        # Platform-specific health check configurations
        self.platform_configs = {
            PlatformType.HUAWEI_NETECO: {
                "endpoint": "/api/health",
                "port": 8080,
                "expected_status": ["OK", "UP", "healthy"],
                "timeout": 15,
            },
            PlatformType.HUAWEI_IMASTER: {
                "endpoint": "/nbi/v1/health",
                "port": 8443,
                "expected_status": ["normal", "healthy"],
                "timeout": 20,
            },
            PlatformType.HUAWEI_MAE: {
                "endpoint": "/mae/api/v1/health",
                "port": 8080,
                "expected_status": ["OK"],
                "timeout": 30,
            },
            PlatformType.ZTE_ELASTICNET: {
                "endpoint": "/elasticnet/health",
                "port": 8080,
                "expected_status": ["UP", "RUNNING"],
                "timeout": 20,
            },
            PlatformType.ZTE_ZENICONE: {
                "endpoint": "/zenicone/api/health",
                "port": 8080,
                "expected_status": ["healthy"],
                "timeout": 20,
            },
            PlatformType.NOKIA_EMS: {
                "endpoint": "/ems/api/health",
                "port": 8080,
                "expected_status": ["OK"],
                "timeout": 15,
            },
        }
    
    def run(self, target: InfrastructureNode, **kwargs) -> CheckResult:
        """
        Execute health check for OSS application.
        """
        platform = target.platform
        config = self.platform_configs.get(platform)
        
        if not config:
            return CheckResult(
                check_name=self.name,
                target=target.ip_address,
                status=Status.ERROR,
                severity=Severity.WARNING,
                message=f"Unsupported platform: {platform.value}",
                details={"platform": platform.value},
            )
        
        # Build health check URL
        protocol = "https" if config.get("port", 8080) == 8443 else "http"
        url = f"{protocol}://{target.ip_address}:{config['port']}{config['endpoint']}"
        
        # Get credentials from secrets (if needed)
        username = kwargs.get("username")
        password = kwargs.get("password")
        
        try:
            # Attempt to get health endpoint
            auth = (username, password) if username and password else None
            response = requests.get(
                url,
                auth=auth,
                timeout=self.timeout,
                verify=False,  # For internal networks with self-signed certs
                headers={"Accept": "application/json"},
            )
            
            # Parse response
            response_data = {}
            if response.headers.get("content-type", "").startswith("application/json"):
                response_data = response.json()
            
            # Check status
            status_text = response_data.get("status", response_data.get("health", "unknown"))
            expected = config["expected_status"]
            
            if response.status_code == 200 and any(s in status_text.upper() for s in [x.upper() for x in expected]):
                return CheckResult(
                    check_name=self.name,
                    target=target.ip_address,
                    status=Status.PASS,
                    severity=Severity.INFO,
                    message=f"{platform.value} health check passed",
                    details={
                        "url": url,
                        "status_code": response.status_code,
                        "response": response_data,
                    },
                )
            else:
                return CheckResult(
                    check_name=self.name,
                    target=target.ip_address,
                    status=Status.FAIL,
                    severity=Severity.CRITICAL,
                    message=f"{platform.value} health check failed: HTTP {response.status_code}",
                    details={
                        "url": url,
                        "status_code": response.status_code,
                        "response": response_data,
                    },
                    remediation_hint=f"Check {platform.value} service logs and ensure application is running. URL: {url}",
                )
                
        except requests.exceptions.Timeout:
            return CheckResult(
                check_name=self.name,
                target=target.ip_address,
                status=Status.FAIL,
                severity=Severity.CRITICAL,
                message=f"{platform.value} health check timeout after {self.timeout}s",
                details={"url": url, "timeout": self.timeout},
                remediation_hint="Check network connectivity and application responsiveness.",
            )
        except requests.exceptions.ConnectionError as e:
            return CheckResult(
                check_name=self.name,
                target=target.ip_address,
                status=Status.FAIL,
                severity=Severity.CRITICAL,
                message=f"{platform.value} connection failed",
                details={"url": url, "error": str(e)},
                remediation_hint="Verify the application port is open and listening.",
            )
        except Exception as e:
            self.logger.exception(f"Unexpected error: {e}")
            return CheckResult(
                check_name=self.name,
                target=target.ip_address,
                status=Status.ERROR,
                severity=Severity.WARNING,
                message=f"Check execution error: {str(e)}",
                details={"url": url},
            )