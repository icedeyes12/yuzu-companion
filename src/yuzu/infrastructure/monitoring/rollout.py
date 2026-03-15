class GradualRolloutManager:
    """Manage gradual rollout of new features.

    Usage:
        manager = GradualRolloutManager()

        # Configure rollout
        manager.configure_rollout(
            feature="USE_NEW_CHAT_HANDLER",
            stages=[10, 25, 50, 75, 100],
            stage_duration_minutes=30
        )

        # Check if user gets new feature
        if manager.should_use_new("USE_NEW_CHAT_HANDLER", user_id):
            # Use new implementation
            pass
    """

    def __init__(self, config_path: str = "rollout_config.json"):
        self._config_path = config_path
        self._configs: Dict[str, Dict] = {}
        self._active: Dict[str, "RolloutStage"] = {}
        self._lock = threading.Lock()
        self._enabled: Dict[str, bool] = {}
        self._kill_switches: Dict[str, bool] = {}

    def configure_rollout(
        self,
        feature: str,
        stages: List[int] = None,
        stage_duration_minutes: int = 30,
        criteria: Dict[str, Any] = None
    ) -> None:
        """Configure rollout for a feature."""
        if stages is None:
            stages = [10, 25, 50, 75, 100]

        config = {
            "feature": feature,
            "stages": stages,
            "stage_duration_minutes": stage_duration_minutes,
            "criteria": criteria or {"max_error_rate": 0.05, "min_success_rate": 0.95},
            "created_at": datetime.now().isoformat(),
        }

        with self._lock:
            self._configs[feature] = config
            self._enabled[feature] = False
            self._kill_switches[feature] = False

    def start_rollout(self, feature: str) -> bool:
        """Start rollout for a feature."""
        with self._lock:
            if feature not in self._configs:
                return False

            config = self._configs[feature]
            first_stage = config["stages"][0]

            self._enabled[feature] = True
            print(f"[Rollout] Started for {feature} at {first_stage}%")
            return True

    def should_use_new(self, feature: str, user_id: str) -> bool:
        """Check if user should get new implementation."""
        with self._lock:
            if self._kill_switches.get(feature, False):
                return False
            return self._enabled.get(feature, False)

    def rollback(self, feature: str, reason: str = "") -> bool:
        """Emergency rollback to old implementation."""
        with self._lock:
            self._kill_switches[feature] = True
            self._enabled[feature] = False

        print(f"[Rollout] {feature} ROLLED BACK: {reason}")
        return True

    def get_status(self) -> Dict[str, Any]:
        """Get current rollout status."""
        return {
            "features": list(self._configs.keys()),
            "enabled": list(k for k, v in self._enabled.items() if v),
            "kill_switched": list(k for k, v in self._kill_switches.items() if v),
        }


# Singleton singleton
_rollout_manager: Optional["GradualRolloutManager"] = None


def get_rollout_manager() -> "GradualRolloutManager":
    """Get global rollout manager."""
    global _rollout_manager
    if _rollout_manager is None:
        _rollout_manager = GradualRolloutManager()
    return _rollout_manager
