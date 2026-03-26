"""
BMC/IPMI health checks for hardware monitoring.
"""

import subprocess
import re
from typing import Dict, Any

from checks.base import BaseCheck, CheckResult, Status, Severity

class BMCCheck(BaseCheck):
    """
    Health check for BMC/IPMI interfaces.
    Monitors hardware health: fans, temperature, power supplies, etc.
    """
    
    def __init__(self, name: str = "bmc_health", timeout: int = 30):
        super().__init__(name, timeout)
    
    def _run_ipmi_command(self, ip: str, username: str, password: str, command: str) -> str:
        """
        Run IPMI command and return output.
        Uses ipmitool for remote BMC access.
        """
        cmd = [
            "ipmitool",
            "-H", ip,
            "-U", username,
            "-P", password,
            "-I", "lanplus",
            command,
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=self.timeout,
        )
        
        if result.returncode != 0:
            raise Exception(f"IPMI command failed: {result.stderr}")
        
        return result.stdout
    
    def _parse_sensor_data(self, output: str) -> Dict[str, Any]:
        """
        Parse ipmitool sdr output to extract sensor readings.
        """
        sensors = {}
        
        # Patterns for different sensor types
        temp_pattern = re.compile(r'(\w+)\s+\|\s+(\d+\.\d+)\s+degrees')
        fan_pattern = re.compile(r'(\w+)\s+\|\s+(\d+)\s+RPM')
        voltage_pattern = re.compile(r'(\w+)\s+\|\s+([\d\.]+)\s+Volts')
        power_pattern = re.compile(r'(\w+)\s+\|\s+(\d+)\s+Watts')
        
        for line in output.split('\n'):
            # Temperature sensors
            match = temp_pattern.search(line)
            if match:
                sensors[match.group(1)] = {
                    "type": "temperature",
                    "value": float(match.group(2)),
                    "unit": "C",
                }
            
            # Fan sensors
            match = fan_pattern.search(line)
            if match:
                sensors[match.group(1)] = {
                    "type": "fan",
                    "value": int(match.group(2)),
                    "unit": "RPM",
                }
            
            # Voltage sensors
            match = voltage_pattern.search(line)
            if match:
                sensors[match.group(1)] = {
                    "type": "voltage",
                    "value": float(match.group(2)),
                    "unit": "V",
                }
        
        return sensors
    
    def run(self, target: str, **kwargs) -> CheckResult:
        """
        Execute BMC health check.
        
        Expected kwargs:
            - username: IPMI username
            - password: IPMI password
        """
        username = kwargs.get("username")
        password = kwargs.get("password")
        
        if not username or not password:
            raise ValueError("Username and password required for BMC checks")
        
        details = {}
        failures = []
        
        try:
            # Get sensor data
            self.logger.info(f"Checking BMC sensors on {target}")
            sensor_output = self._run_ipmi_command(target, username, password, "sdr")
            sensors = self._parse_sensor_data(sensor_output)
            details["sensors"] = sensors
            
            # Check thresholds
            thresholds = kwargs.get("thresholds", {
                "temperature_max": 85,  # Celsius
                "fan_min": 1000,        # RPM
            })
            
            # Check for high temperatures
            for sensor_name, sensor_data in sensors.items():
                if sensor_data["type"] == "temperature":
                    if sensor_data["value"] > thresholds["temperature_max"]:
                        failures.append(f"High temperature on {sensor_name}: {sensor_data['value']}C")
                
                elif sensor_data["type"] == "fan":
                    if sensor_data["value"] < thresholds["fan_min"]:
                        failures.append(f"Low fan speed on {sensor_name}: {sensor_data['value']} RPM")
            
            # Get system event log for errors
            sel_output = self._run_ipmi_command(target, username, password, "sel list")
            error_count = len([l for l in sel_output.split('\n') if 'Assertion' in l])
            details["sel_error_count"] = error_count
            
            if error_count > 0:
                failures.append(f"{error_count} errors found in System Event Log")
            
            # Determine overall status
            if failures:
                return CheckResult(
                    check_name=self.name,
                    target=target,
                    status=Status.WARN,
                    severity=Severity.WARNING,
                    message=f"BMC issues detected: {'; '.join(failures[:3])}",
                    details=details,
                    remediation_hint="Check physical hardware status. Inspect fans, temperatures, and power supplies.",
                )
            else:
                return CheckResult(
                    check_name=self.name,
                    target=target,
                    status=Status.PASS,
                    severity=Severity.INFO,
                    message="BMC health check passed - all sensors normal",
                    details=details,
                )
                
        except subprocess.TimeoutExpired:
            return CheckResult(
                check_name=self.name,
                target=target,
                status=Status.FAIL,
                severity=Severity.CRITICAL,
                message=f"BMC check timeout after {self.timeout}s",
                details={"error": "Timeout"},
                remediation_hint="Check network connectivity to BMC interface.",
            )
        except Exception as e:
            return CheckResult(
                check_name=self.name,
                target=target,
                status=Status.ERROR,
                severity=Severity.WARNING,
                message=f"BMC check failed: {str(e)}",
                details={"error": str(e)},
            )