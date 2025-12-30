"""
Task #31: Fallback to Claude Haiku on Budget Limit

Manages API budget tracking and automatic model fallback.
When Sonnet budget is exceeded, automatically switches to Haiku.

Features:
- Daily/monthly budget tracking
- Per-user budget limits
- Automatic Sonnet → Haiku fallback
- Cost estimation and reporting
"""

import os
import time
import threading
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from enum import Enum
import logging

logger = logging.getLogger(__name__)


# Pricing per 1M tokens (USD)
MODEL_PRICING = {
    "sonnet": {"input": 3.0, "output": 15.0},
    "haiku": {"input": 0.25, "output": 1.25},
}


class ModelTier(str, Enum):
    """Model tier for budget management."""
    SONNET = "sonnet"
    HAIKU = "haiku"


@dataclass
class BudgetConfig:
    """Budget configuration."""
    daily_budget_usd: float = 10.0  # Daily budget in USD
    monthly_budget_usd: float = 200.0  # Monthly budget in USD
    sonnet_threshold_pct: float = 0.7  # Switch to Haiku when 70% of budget used
    per_user_daily_usd: float = 2.0  # Per-user daily limit
    fallback_enabled: bool = True  # Enable automatic fallback to Haiku
    

@dataclass
class UsageRecord:
    """Usage record for tracking."""
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    model: str = "sonnet"
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cost_usd": self.cost_usd,
            "model": self.model,
            "timestamp": self.timestamp,
        }


@dataclass
class BudgetStatus:
    """Current budget status."""
    daily_spent_usd: float
    monthly_spent_usd: float
    daily_remaining_usd: float
    monthly_remaining_usd: float
    daily_budget_pct: float
    monthly_budget_pct: float
    recommended_model: ModelTier
    is_over_budget: bool
    fallback_active: bool
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "daily_spent_usd": round(self.daily_spent_usd, 4),
            "monthly_spent_usd": round(self.monthly_spent_usd, 4),
            "daily_remaining_usd": round(self.daily_remaining_usd, 4),
            "monthly_remaining_usd": round(self.monthly_remaining_usd, 4),
            "daily_budget_pct": round(self.daily_budget_pct, 2),
            "monthly_budget_pct": round(self.monthly_budget_pct, 2),
            "recommended_model": self.recommended_model.value,
            "is_over_budget": self.is_over_budget,
            "fallback_active": self.fallback_active,
        }


class BudgetManager:
    """
    Manages API budget and model fallback.
    
    Tracks spending and automatically recommends/switches to Haiku
    when budget thresholds are exceeded.
    """
    
    def __init__(self, config: Optional[BudgetConfig] = None):
        """
        Initialize budget manager.
        
        Args:
            config: Budget configuration
        """
        self.config = config or BudgetConfig()
        
        # Daily tracking (resets at midnight UTC)
        self._daily_usage: Dict[str, float] = {}  # user_id -> cost
        self._daily_total: float = 0.0
        self._daily_reset_date: str = self._get_today()
        
        # Monthly tracking (resets on 1st of month)
        self._monthly_usage: Dict[str, float] = {}
        self._monthly_total: float = 0.0
        self._monthly_reset_month: str = self._get_month()
        
        # Thread safety
        self._lock = threading.Lock()
        
        logger.info(
            f"Initialized BudgetManager: daily=${self.config.daily_budget_usd}, "
            f"monthly=${self.config.monthly_budget_usd}, "
            f"threshold={self.config.sonnet_threshold_pct*100}%"
        )
    
    def _get_today(self) -> str:
        """Get today's date string."""
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")
    
    def _get_month(self) -> str:
        """Get current month string."""
        return datetime.now(timezone.utc).strftime("%Y-%m")
    
    def _check_reset(self) -> None:
        """Check and reset counters if needed."""
        today = self._get_today()
        month = self._get_month()
        
        # Reset daily counters
        if today != self._daily_reset_date:
            logger.info(f"Resetting daily budget counters for {today}")
            self._daily_usage.clear()
            self._daily_total = 0.0
            self._daily_reset_date = today
        
        # Reset monthly counters
        if month != self._monthly_reset_month:
            logger.info(f"Resetting monthly budget counters for {month}")
            self._monthly_usage.clear()
            self._monthly_total = 0.0
            self._monthly_reset_month = month
    
    def calculate_cost(
        self,
        input_tokens: int,
        output_tokens: int,
        model: str = "sonnet"
    ) -> float:
        """
        Calculate cost for token usage.
        
        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            model: Model used (sonnet/haiku)
            
        Returns:
            Cost in USD
        """
        pricing = MODEL_PRICING.get(model, MODEL_PRICING["sonnet"])
        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]
        return input_cost + output_cost
    
    def record_usage(
        self,
        input_tokens: int,
        output_tokens: int,
        model: str = "sonnet",
        user_id: str = "anonymous"
    ) -> UsageRecord:
        """
        Record token usage and cost.
        
        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            model: Model used
            user_id: User identifier
            
        Returns:
            UsageRecord with cost information
        """
        cost = self.calculate_cost(input_tokens, output_tokens, model)
        
        with self._lock:
            self._check_reset()
            
            # Update daily totals
            self._daily_total += cost
            self._daily_usage[user_id] = self._daily_usage.get(user_id, 0.0) + cost
            
            # Update monthly totals
            self._monthly_total += cost
            self._monthly_usage[user_id] = self._monthly_usage.get(user_id, 0.0) + cost
        
        record = UsageRecord(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            model=model,
        )
        
        logger.debug(
            f"Recorded usage: user={user_id}, model={model}, "
            f"tokens={input_tokens}+{output_tokens}, cost=${cost:.4f}"
        )
        
        return record

    def get_status(self, user_id: str = "anonymous") -> BudgetStatus:
        """
        Get current budget status.
        
        Args:
            user_id: User identifier
            
        Returns:
            BudgetStatus with spending and recommendations
        """
        with self._lock:
            self._check_reset()
            
            daily_spent = self._daily_total
            monthly_spent = self._monthly_total
        
        daily_remaining = max(0, self.config.daily_budget_usd - daily_spent)
        monthly_remaining = max(0, self.config.monthly_budget_usd - monthly_spent)
        
        daily_pct = (daily_spent / self.config.daily_budget_usd) * 100 if self.config.daily_budget_usd > 0 else 0
        monthly_pct = (monthly_spent / self.config.monthly_budget_usd) * 100 if self.config.monthly_budget_usd > 0 else 0
        
        # Determine if over budget
        is_over_budget = daily_spent >= self.config.daily_budget_usd or monthly_spent >= self.config.monthly_budget_usd
        
        # Determine recommended model
        threshold_pct = self.config.sonnet_threshold_pct * 100
        fallback_active = (daily_pct >= threshold_pct or monthly_pct >= threshold_pct) and self.config.fallback_enabled
        
        recommended_model = ModelTier.HAIKU if fallback_active else ModelTier.SONNET
        
        return BudgetStatus(
            daily_spent_usd=daily_spent,
            monthly_spent_usd=monthly_spent,
            daily_remaining_usd=daily_remaining,
            monthly_remaining_usd=monthly_remaining,
            daily_budget_pct=daily_pct,
            monthly_budget_pct=monthly_pct,
            recommended_model=recommended_model,
            is_over_budget=is_over_budget,
            fallback_active=fallback_active,
        )
    
    def get_recommended_model(self, user_id: str = "anonymous") -> ModelTier:
        """
        Get recommended model based on budget.
        
        Args:
            user_id: User identifier
            
        Returns:
            ModelTier (SONNET or HAIKU)
        """
        status = self.get_status(user_id)
        return status.recommended_model
    
    def check_user_budget(self, user_id: str) -> bool:
        """
        Check if user is within their daily budget.
        
        Args:
            user_id: User identifier
            
        Returns:
            True if within budget, False if exceeded
        """
        with self._lock:
            self._check_reset()
            user_spent = self._daily_usage.get(user_id, 0.0)
        
        return user_spent < self.config.per_user_daily_usd
    
    def get_user_spending(self, user_id: str) -> Dict[str, float]:
        """
        Get user's spending summary.
        
        Args:
            user_id: User identifier
            
        Returns:
            Dict with daily and monthly spending
        """
        with self._lock:
            self._check_reset()
            daily = self._daily_usage.get(user_id, 0.0)
            monthly = self._monthly_usage.get(user_id, 0.0)
        
        return {
            "daily_spent_usd": round(daily, 4),
            "monthly_spent_usd": round(monthly, 4),
            "daily_limit_usd": self.config.per_user_daily_usd,
            "daily_remaining_usd": round(max(0, self.config.per_user_daily_usd - daily), 4),
        }
    
    def estimate_request_cost(
        self,
        estimated_input_tokens: int,
        estimated_output_tokens: int = 500,
        model: str = "sonnet"
    ) -> Dict[str, Any]:
        """
        Estimate cost for a request before making it.
        
        Args:
            estimated_input_tokens: Estimated input tokens
            estimated_output_tokens: Estimated output tokens
            model: Model to use
            
        Returns:
            Dict with cost estimates for both models
        """
        sonnet_cost = self.calculate_cost(
            estimated_input_tokens, estimated_output_tokens, "sonnet"
        )
        haiku_cost = self.calculate_cost(
            estimated_input_tokens, estimated_output_tokens, "haiku"
        )
        
        return {
            "estimated_input_tokens": estimated_input_tokens,
            "estimated_output_tokens": estimated_output_tokens,
            "sonnet_cost_usd": round(sonnet_cost, 6),
            "haiku_cost_usd": round(haiku_cost, 6),
            "savings_with_haiku_usd": round(sonnet_cost - haiku_cost, 6),
            "savings_pct": round((1 - haiku_cost / sonnet_cost) * 100, 1) if sonnet_cost > 0 else 0,
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get overall budget statistics."""
        with self._lock:
            self._check_reset()
            
            return {
                "daily": {
                    "spent_usd": round(self._daily_total, 4),
                    "budget_usd": self.config.daily_budget_usd,
                    "remaining_usd": round(max(0, self.config.daily_budget_usd - self._daily_total), 4),
                    "users": len(self._daily_usage),
                    "date": self._daily_reset_date,
                },
                "monthly": {
                    "spent_usd": round(self._monthly_total, 4),
                    "budget_usd": self.config.monthly_budget_usd,
                    "remaining_usd": round(max(0, self.config.monthly_budget_usd - self._monthly_total), 4),
                    "users": len(self._monthly_usage),
                    "month": self._monthly_reset_month,
                },
                "config": {
                    "sonnet_threshold_pct": self.config.sonnet_threshold_pct * 100,
                    "per_user_daily_usd": self.config.per_user_daily_usd,
                    "fallback_enabled": self.config.fallback_enabled,
                },
            }
    
    def reset(self, daily: bool = True, monthly: bool = False) -> None:
        """
        Reset budget counters.
        
        Args:
            daily: Reset daily counters
            monthly: Reset monthly counters
        """
        with self._lock:
            if daily:
                self._daily_usage.clear()
                self._daily_total = 0.0
                self._daily_reset_date = self._get_today()
                logger.info("Reset daily budget counters")
            
            if monthly:
                self._monthly_usage.clear()
                self._monthly_total = 0.0
                self._monthly_reset_month = self._get_month()
                logger.info("Reset monthly budget counters")


# Global budget manager instance
_budget_manager: Optional[BudgetManager] = None


def get_budget_manager() -> BudgetManager:
    """Get or create global budget manager."""
    global _budget_manager
    if _budget_manager is None:
        _budget_manager = BudgetManager()
    return _budget_manager


def configure_budget_manager(config: BudgetConfig) -> BudgetManager:
    """Configure and return budget manager."""
    global _budget_manager
    _budget_manager = BudgetManager(config)
    return _budget_manager
