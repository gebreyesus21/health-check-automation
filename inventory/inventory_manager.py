"""
Manages the 150+ infrastructure nodes from your environment.
"""

import yaml
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import asdict

from inventory.models import InfrastructureNode, PlatformType, NodeRole

class InventoryManager:
    """
    Loads and manages the infrastructure inventory.
    Can be generated from your CSV/Excel inventory.
    """
    
    def __init__(self, inventory_path: Optional[Path] = None):
        self.inventory_path = inventory_path or Path(__file__).parent.parent / "inventory.yaml"
        self.nodes: List[InfrastructureNode] = []
        self._load_inventory()
    
    def _load_inventory(self):
        """Load inventory from YAML file."""
        if not self.inventory_path.exists():
            self._generate_default_inventory()
        else:
            with open(self.inventory_path) as f:
                data = yaml.safe_load(f)
                for node_data in data.get("nodes", []):
                    self.nodes.append(InfrastructureNode(
                        name=node_data["name"],
                        ip_address=node_data["ip_address"],
                        platform=PlatformType(node_data["platform"]),
                        role=NodeRole(node_data["role"]),
                        region=node_data.get("region", "unknown"),
                        check_enabled=node_data.get("check_enabled", True),
                        custom_params=node_data.get("custom_params", {}),
                    ))
    
    def _generate_default_inventory(self):
        """Generate inventory from the server list you provided."""
        # This would parse your 150+ server list
        # For now, let's create a structured version
        
        nodes = []
        
        # Huawei NetEco nodes
        neteco_ips = ["10.xx.xx.xx", "10.xx.xx.xx", "10.xx.xx.xx"]  # Replace with actual
        for idx, ip in enumerate(neteco_ips):
            nodes.append(InfrastructureNode(
                name=f"neteco-master-{idx}" if idx == 0 else f"neteco-node-{idx}",
                ip_address=ip,
                platform=PlatformType.HUAWEI_NETECO,
                role=NodeRole.PRIMARY if idx == 0 else NodeRole.SECONDARY,
                region="central",
                custom_params={
                    "health_endpoint": "/api/health",
                    "application_port": 8080,
                }
            ))
        
        # Huawei iMaster nodes
        imaster_ips = ["10.xx.xx.xx", "10.xx.xx.xx"]  # Replace with actual
        for idx, ip in enumerate(imaster_ips):
            nodes.append(InfrastructureNode(
                name=f"imaster-{idx}",
                ip_address=ip,
                platform=PlatformType.HUAWEI_IMASTER,
                role=NodeRole.PRIMARY if idx == 0 else NodeRole.SECONDARY,
                region="central",
                custom_params={
                    "health_endpoint": "/nbi/v1/health",
                    "api_port": 8443,
                }
            ))
        
        # Add all your nodes based on the list...
        # This would be generated programmatically from your provided list
        
        # Save to file
        with open(self.inventory_path, 'w') as f:
            yaml.dump({"nodes": [asdict(n) for n in nodes]}, f, default_flow_style=False)
    
    def get_nodes_by_platform(self, platform: PlatformType) -> List[InfrastructureNode]:
        """Get all nodes of a specific platform."""
        return [n for n in self.nodes if n.platform == platform and n.check_enabled]
    
    def get_nodes_by_region(self, region: str) -> List[InfrastructureNode]:
        """Get all nodes in a specific region."""
        return [n for n in self.nodes if n.region == region and n.check_enabled]
    
    def get_all_nodes(self) -> List[InfrastructureNode]:
        """Get all enabled nodes."""
        return [n for n in self.nodes if n.check_enabled]