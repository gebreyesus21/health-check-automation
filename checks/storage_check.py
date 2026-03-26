"""
Health checks for storage systems (CEPH, disk arrays).
"""

import subprocess
import json
from typing import Dict, Any

from checks.base import BaseCheck, CheckResult, Status, Severity

class StorageCheck(BaseCheck):
    """
    Health check for Ceph clusters and disk arrays.
    """
    
    def __init__(self, name: str = "storage_health", timeout: int = 60):
        super().__init__(name, timeout)
    
    def _check_ceph_health(self, target: str, keyring_path: str) -> Dict[str, Any]:
        """
        Check Ceph cluster health using ceph commands.
        """
        # Check overall cluster health
        cmd = ["ceph", "-s", "--format", "json", "--keyring", keyring_path]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=self.timeout,
        )
        
        if result.returncode != 0:
            raise Exception(f"Ceph command failed: {result.stderr}")
        
        ceph_status = json.loads(result.stdout)
        
        # Extract key metrics
        health = ceph_status.get("health", {}).get("status", "UNKNOWN")
        pgmap = ceph_status.get("pgmap", {})
        
        return {
            "health_status": health,
            "total_bytes": pgmap.get("bytes_total", 0),
            "used_bytes": pgmap.get("bytes_used", 0),
            "avail_bytes": pgmap.get("bytes_avail", 0),
            "pgs_total": pgmap.get("num_pgs", 0),
            "pgs_active_clean": pgmap.get("num_pgs_active_clean", 0),
        }
    
    def _check_disk_array(self, target: str, snmp_community: str) -> Dict[str, Any]:
        """
        Check disk array health via SNMP.
        """
        # OIDs for disk array monitoring
        oids = {
            "controller_status": "1.3.6.1.4.1.2011.2.23.1.1.1.0",  # Huawei Disk Array OID
            "disk_count": "1.3.6.1.4.1.2011.2.23.1.1.2.0",
            "failed_disks": "1.3.6.1.4.1.2011.2.23.1.1.3.0",
            "raid_status": "1.3.6.1.4.1.2011.2.23.1.2.1.0",
        }
        
        results = {}
        for name, oid in oids.items():
            cmd = ["snmpget", "-v", "2c", "-c", snmp_community, target, oid]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                # Parse SNMP output
                output = result.stdout
                if "INTEGER:" in output:
                    value = output.split("INTEGER:")[1].strip()
                    results[name] = value
        
        return results
    
    def run(self, target: str, **kwargs) -> CheckResult:
        """
        Execute storage health check.
        
        Expected kwargs:
            - storage_type: "ceph" or "disk_array"
            - keyring_path: Path to Ceph keyring (for Ceph)
            - snmp_community: SNMP community string (for disk arrays)
        """
        storage_type = kwargs.get("storage_type", "ceph")
        
        try:
            if storage_type == "ceph":
                keyring_path = kwargs.get("keyring_path")
                if not keyring_path:
                    raise ValueError("keyring_path required for Ceph checks")
                
                metrics = self._check_ceph_health(target, keyring_path)
                
                # Check health status
                health_status = metrics.get("health_status", "UNKNOWN")
                
                if health_status == "HEALTH_OK":
                    return CheckResult(
                        check_name=self.name,
                        target=target,
                        status=Status.PASS,
                        severity=Severity.INFO,
                        message=f"Ceph cluster healthy",
                        details=metrics,
                    )
                elif health_status == "HEALTH_WARN":
                    return CheckResult(
                        check_name=self.name,
                        target=target,
                        status=Status.WARN,
                        severity=Severity.WARNING,
                        message=f"Ceph cluster has warnings",
                        details=metrics,
                        remediation_hint="Check Ceph health details with 'ceph health detail'",
                    )
                else:
                    return CheckResult(
                        check_name=self.name,
                        target=target,
                        status=Status.FAIL,
                        severity=Severity.CRITICAL,
                        message=f"Ceph cluster unhealthy: {health_status}",
                        details=metrics,
                        remediation_hint="Check Ceph status and investigate OSD/monitor issues",
                    )
            
            elif storage_type == "disk_array":
                snmp_community = kwargs.get("snmp_community")
                if not snmp_community:
                    raise ValueError("snmp_community required for disk array checks")
                
                metrics = self._check_disk_array(target, snmp_community)
                
                # Check controller status
                controller_status = metrics.get("controller_status", "unknown")
                failed_disks = metrics.get("failed_disks", "0")
                
                if controller_status == "1" and failed_disks == "0":
                    return CheckResult(
                        check_name=self.name,
                        target=target,
                        status=Status.PASS,
                        severity=Severity.INFO,
                        message=f"Disk array healthy",
                        details=metrics,
                    )
                else:
                    return CheckResult(
                        check_name=self.name,
                        target=target,
                        status=Status.FAIL,
                        severity=Severity.CRITICAL,
                        message=f"Disk array issues detected",
                        details=metrics,
                        remediation_hint="Check disk array management interface for failed disks or controller issues",
                    )
            
            else:
                raise ValueError(f"Unsupported storage type: {storage_type}")
                
        except subprocess.TimeoutExpired:
            return CheckResult(
                check_name=self.name,
                target=target,
                status=Status.FAIL,
                severity=Severity.CRITICAL,
                message=f"Storage check timeout after {self.timeout}s",
                details={"storage_type": storage_type},
                remediation_hint="Check network connectivity and storage management interface.",
            )
        except Exception as e:
            return CheckResult(
                check_name=self.name,
                target=target,
                status=Status.ERROR,
                severity=Severity.WARNING,
                message=f"Storage check failed: {str(e)}",
                details={"error": str(e)},
            )