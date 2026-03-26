"""
Configuration management with support for multiple environments.
"""

import os
from pathlib import Path
from typing import Optional, Dict, Any
from dotenv import load_dotenv
import json

# Load environment variables
load_dotenv()

class Settings:
    """Centralized configuration with environment-specific overrides."""
    
    # Environment
    ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
    DEBUG = ENVIRONMENT == "development"
    
    # Application settings
    APP_NAME = "EthioTelecom Health Check Automation"
    APP_VERSION = "2.0.0"
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    
    # Performance settings
    CHECK_TIMEOUT_SECONDS = int(os.getenv("CHECK_TIMEOUT_SECONDS", "30"))
    MAX_RETRIES = int(os.getenv("MAX_RETRIES", "2"))
    MAX_WORKERS = int(os.getenv("MAX_WORKERS", "10"))
    
    # Alerting settings
    ALERT_COOLDOWN_SECONDS = int(os.getenv("ALERT_COOLDOWN_SECONDS", "300"))  # 5 minutes
    BATCH_ALERT_INTERVAL = int(os.getenv("BATCH_ALERT_INTERVAL", "3600"))  # 1 hour
    
    # Slack configuration
    SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")
    SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
    SLACK_CHANNEL = os.getenv("SLACK_CHANNEL", "#infrastructure-alerts")
    SLACK_ALERT_THREAD = os.getenv("SLACK_ALERT_THREAD", "false").lower() == "true"
    
    # PRTG configuration
    PRTG_SERVER = os.getenv("PRTG_SERVER")
    PRTG_USERNAME = os.getenv("PRTG_USERNAME")
    PRTG_PASSWORD = os.getenv("PRTG_PASSWORD")
    PRTG_ENABLED = os.getenv("PRTG_ENABLED", "false").lower() == "true"
    
    # ServiceNow configuration
    SERVICENOW_INSTANCE = os.getenv("SERVICENOW_INSTANCE")
    SERVICENOW_USERNAME = os.getenv("SERVICENOW_USERNAME")
    SERVICENOW_PASSWORD = os.getenv("SERVICENOW_PASSWORD")
    SERVICENOW_ENABLED = os.getenv("SERVICENOW_ENABLED", "false").lower() == "true"
    
    # Secrets management
    SECRETS_PATH = Path(os.getenv("SECRETS_PATH", "/run/secrets"))
    USE_VAULT = os.getenv("USE_VAULT", "false").lower() == "true"
    VAULT_ADDR = os.getenv("VAULT_ADDR", "https://vault.ethiotelecom.et:8200")
    VAULT_TOKEN = os.getenv("VAULT_TOKEN")
    
    # Database (for storing results)
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///health_checks.db")
    
    # Monitoring thresholds
    THRESHOLDS = {
        "cpu_percent": int(os.getenv("CPU_THRESHOLD", "80")),
        "memory_percent": int(os.getenv("MEMORY_THRESHOLD", "85")),
        "disk_percent": int(os.getenv("DISK_THRESHOLD", "85")),
        "load_avg": float(os.getenv("LOAD_THRESHOLD", "4.0")),
        "temperature_celsius": int(os.getenv("TEMP_THRESHOLD", "80")),
        "fan_rpm": int(os.getenv("FAN_THRESHOLD", "1000")),
    }
    
    @classmethod
    def get_secret(cls, secret_name: str) -> Optional[str]:
        """
        Retrieve secret from multiple sources:
        1. Kubernetes secrets (file-based)
        2. HashiCorp Vault
        3. Environment variables
        """
        # Try file-based secrets (Kubernetes)
        secret_file = cls.SECRETS_PATH / secret_name
        if secret_file.exists():
            return secret_file.read_text().strip()
        
        # Try Vault
        if cls.USE_VAULT and cls.VAULT_TOKEN:
            try:
                import hvac
                client = hvac.Client(
                    url=cls.VAULT_ADDR,
                    token=cls.VAULT_TOKEN
                )
                if client.is_authenticated():
                    secret = client.secrets.kv.v2.read_secret_version(
                        path=secret_name,
                        mount_point="secret"
                    )
                    if secret and secret.get("data", {}).get("data"):
                        return secret["data"]["data"].get("value")
            except Exception:
                pass  # Fall through to environment
        
        # Try environment variable
        env_var_name = secret_name.upper().replace("-", "_")
        return os.getenv(env_var_name)
    
    @classmethod
    def get_platform_credentials(cls, platform: str) -> Dict[str, str]:
        """Get credentials for a specific platform."""
        return {
            "username": cls.get_secret(f"{platform}_username"),
            "password": cls.get_secret(f"{platform}_password"),
            "api_key": cls.get_secret(f"{platform}_api_key"),
        }
    
    @classmethod
    def validate(cls) -> bool:
        """Validate critical configuration."""
        errors = []
        
        if cls.SLACK_WEBHOOK_URL:
            if not cls.SLACK_WEBHOOK_URL.startswith("https://hooks.slack.com/"):
                errors.append("SLACK_WEBHOOK_URL appears invalid")
        
        if cls.PRTG_ENABLED and not cls.PRTG_SERVER:
            errors.append("PRTG_ENABLED is true but PRTG_SERVER not set")
        
        if errors:
            for error in errors:
                print(f"Configuration error: {error} - settings.py:130")
            return False
        
        return True


settings = Settings()