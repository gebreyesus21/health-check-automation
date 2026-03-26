"""
Data models for Ethio Telecom OSS infrastructure inventory.
"""

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Dict, Any

class PlatformType(Enum):
    """Types of OSS platforms in your environment."""
    HUAWEI_NETECO = "huawei_neteco"
    HUAWEI_IMASTER = "huawei_imaster"
    HUAWEI_MAE = "huawei_mae"
    HUAWEI_OSMU = "huawei_osmu"
    ZTE_ELASTICNET = "zte_elasticnet"
    ZTE_ZENICONE = "zte_zenicone"
    ZTE_NETNUMEN = "zte_netnumen"
    ZTE_U31 = "zte_u31"
    NOKIA_EMS = "nokia_ems"
    NOKIA_ALTIPLANO = "nokia_altiplano"
    STORAGE = "storage"
    VM = "vm"
    BMC = "bmc"

class NodeRole(Enum):
    """Node role in the infrastructure."""
    PRIMARY = "primary"
    SECONDARY = "secondary"
    CONTROLLER = "controller"
    STORAGE = "storage"
    BMC = "bmc"
    VM = "vm"

@dataclass
class InfrastructureNode:
    """Represents a single infrastructure node."""
    name: str
    ip_address: str
    platform: PlatformType
    role: NodeRole
    region: str  # North Circle, SSWR, AA, etc.
    check_enabled: bool = True
    custom_params: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.custom_params is None:
            self.custom_params = {}

@dataclass
class HealthCheckResult:
    """Extended result for telecom OSS checks."""
    node: InfrastructureNode
    check_type: str
    status: str  # pass, fail, warn, error
    severity: str  # info, warning, critical
    message: str
    metrics: Dict[str, Any]
    timestamp: float
    remediation_steps: List[str] = None