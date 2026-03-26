"""
Circuit breaker pattern to prevent cascading failures.
"""

import time
import functools
from enum import Enum
from typing import Callable, Any, Optional
from dataclasses import dataclass

class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, don't attempt
    HALF_OPEN = "half_open" # Testing if recovered

@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 5          # Number of failures before opening
    recovery_timeout: int = 60          # Seconds to wait before trying again
    half_open_max_calls: int = 3        # Max calls in half-open state
    success_threshold: int = 2          # Successes needed to close

class CircuitBreaker:
    """
    Circuit breaker to protect against repeated failures.
    """
    
    def __init__(self, name: str, config: Optional[CircuitBreakerConfig] = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = 0
        self.half_open_calls = 0
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with circuit breaker protection.
        """
        if self.state == CircuitState.OPEN:
            # Check if recovery timeout has elapsed
            if time.time() - self.last_failure_time >= self.config.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                self.half_open_calls = 0
                self.success_count = 0
            else:
                raise CircuitBreakerOpenError(f"Circuit breaker '{self.name}' is OPEN")
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise e
    
    def _on_success(self):
        """Handle successful execution."""
        if self.state == CircuitState.HALF_OPEN:
            self.half_open_calls += 1
            self.success_count += 1
            
            if self.success_count >= self.config.success_threshold:
                self._close()
        elif self.state == CircuitState.CLOSED:
            self.failure_count = 0
            self.success_count = 0
    
    def _on_failure(self):
        """Handle failed execution."""
        self.last_failure_time = time.time()
        
        if self.state == CircuitState.HALF_OPEN:
            self._open()
        elif self.state == CircuitState.CLOSED:
            self.failure_count += 1
            if self.failure_count >= self.config.failure_threshold:
                self._open()
    
    def _close(self):
        """Close the circuit (normal operation)."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
    
    def _open(self):
        """Open the circuit (stop calling)."""
        self.state = CircuitState.OPEN
        self.failure_count = 0
        self.success_count = 0
    
    def get_state(self) -> Dict[str, Any]:
        """Get current circuit state for monitoring."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure": self.last_failure_time,
        }


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open."""
    pass


def with_circuit_breaker(breaker: CircuitBreaker):
    """Decorator to wrap functions with circuit breaker."""
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return breaker.call(func, *args, **kwargs)
        return wrapper
    return decorator