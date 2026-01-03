"""
QSCI Parameter Registry - Runtime-modifiable configuration system

Features:
- Hot-reload capability for live parameter changes
- Validation with min/max bounds
- Telegram integration for remote parameter control
- Preset configurations (conservative, moderate, aggressive)
- Change callbacks for reactive updates

Author: QSCI Trading System
Version: 3.1.0
"""

import os
import yaml
import json
import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union
from dataclasses import dataclass, field
from threading import Lock
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class ParameterSpec:
    """Specification for a single parameter"""
    name: str
    type: str
    default: Any
    value: Any = None
    min: Optional[float] = None
    max: Optional[float] = None
    description: str = ""
    hot_reload: bool = True
    telegram_editable: bool = True
    category: str = "general"
    last_modified: Optional[datetime] = None
    modified_by: str = "system"

    def __post_init__(self):
        if self.value is None:
            self.value = self.default

    def validate(self, value: Any) -> bool:
        """Validate value against constraints"""
        # Type check
        if self.type == "float":
            try:
                value = float(value)
            except (ValueError, TypeError):
                return False
        elif self.type == "int":
            try:
                value = int(value)
            except (ValueError, TypeError):
                return False
        elif self.type == "bool":
            if not isinstance(value, bool):
                if isinstance(value, str):
                    value = value.lower() in ('true', '1', 'yes', 'on')
                else:
                    return False

        # Range check
        if self.min is not None and value < self.min:
            return False
        if self.max is not None and value > self.max:
            return False

        return True

    def coerce(self, value: Any) -> Any:
        """Coerce value to correct type"""
        if self.type == "float":
            return float(value)
        elif self.type == "int":
            return int(value)
        elif self.type == "bool":
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                return value.lower() in ('true', '1', 'yes', 'on')
            return bool(value)
        return value


class ParameterRegistry:
    """
    Singleton registry for all trading parameters.

    Thread-safe, supports hot-reload and callbacks.

    Usage:
        params = ParameterRegistry()
        params.get('min_qsci_signal')  # Get value
        params.set('min_qsci_signal', 0.15)  # Set value
        params.apply_preset('conservative')  # Apply preset
    """

    _instance = None
    _lock = Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._params: Dict[str, ParameterSpec] = {}
        self._callbacks: List[Callable[[str, Any, Any], None]] = []
        self._presets: Dict[str, Dict[str, Any]] = {}
        self._change_history: List[Dict] = []
        self._schema_path: Optional[Path] = None
        self._param_lock = Lock()

        # Load schema on init
        self._load_default_schema()
        self._initialized = True

    def _load_default_schema(self):
        """Load schema from default location"""
        schema_paths = [
            Path(__file__).parent / 'config' / 'schema.yaml',
            Path(__file__).parent.parent / 'config' / 'schema.yaml',
            Path('/home/pranay/Music/QUANTUM-SENTIMENT-COMPOSITE-INDICATOR--QSCI-/config/schema.yaml'),
        ]

        for path in schema_paths:
            if path.exists():
                self.load_schema(path)
                return

        logger.warning("No schema.yaml found, using hardcoded defaults")
        self._load_hardcoded_defaults()

    def _load_hardcoded_defaults(self):
        """Fallback hardcoded defaults if schema not found"""
        defaults = {
            # Trading
            'account_balance': (10000.0, 'float', 100, 10000000),
            'risk_per_trade': (0.025, 'float', 0.001, 0.1),
            'max_concurrent_positions': (2, 'int', 1, 20),
            'max_position_size_pct': (0.05, 'float', 0.01, 0.25),

            # Signals
            'min_qsci_signal': (0.12, 'float', 0.01, 0.5),
            'min_adx': (20, 'int', 5, 50),
            'max_iv_rank': (0.6, 'float', 0.0, 1.0),
            'min_delta': (0.30, 'float', 0.1, 0.7),
            'max_delta': (0.60, 'float', 0.3, 0.9),
            'min_dte': (5, 'int', 1, 30),
            'max_dte': (21, 'int', 7, 90),

            # Exits
            'tp1_target': (1.5, 'float', 0.5, 5.0),
            'tp2_target': (3.0, 'float', 1.0, 10.0),
            'tp3_target': (5.0, 'float', 2.0, 15.0),
            'sl_multiplier': (1.2, 'float', 0.5, 3.0),
            'trailing_activation': (0.8, 'float', 0.1, 2.0),
            'trailing_distance': (0.35, 'float', 0.1, 0.8),

            # Weights
            'momentum_weight': (0.35, 'float', 0.0, 1.0),
            'trend_weight': (0.30, 'float', 0.0, 1.0),
            'volume_weight': (0.15, 'float', 0.0, 1.0),
            'volatility_weight': (0.10, 'float', 0.0, 1.0),
            'pattern_weight': (0.10, 'float', 0.0, 1.0),

            # Strategy flags
            'use_multi_timeframe': (True, 'bool', None, None),
            'use_sentiment_filter': (False, 'bool', None, None),
            'only_strong_signals': (False, 'bool', None, None),
            'require_trend_alignment': (True, 'bool', None, None),
            'dynamic_position_sizing': (True, 'bool', None, None),

            # Risk
            'max_daily_loss_pct': (0.05, 'float', 0.01, 0.2),
            'max_drawdown_pct': (0.20, 'float', 0.05, 0.5),
        }

        for name, (default, ptype, pmin, pmax) in defaults.items():
            self._params[name] = ParameterSpec(
                name=name,
                type=ptype,
                default=default,
                min=pmin,
                max=pmax,
            )

    def load_schema(self, schema_path: Union[str, Path]):
        """Load parameters from YAML schema"""
        schema_path = Path(schema_path)
        if not schema_path.exists():
            raise FileNotFoundError(f"Schema not found: {schema_path}")

        self._schema_path = schema_path

        with open(schema_path, 'r') as f:
            schema = yaml.safe_load(f)

        # Parse schema sections
        for section, params in schema.items():
            if section in ('version', 'description'):
                continue
            if section == 'presets':
                self._load_presets(params)
                continue

            self._parse_section(section, params)

        logger.info(f"Loaded {len(self._params)} parameters from {schema_path.name}")

    def _parse_section(self, section: str, params: dict, prefix: str = ""):
        """Recursively parse schema section"""
        if not isinstance(params, dict):
            return

        for name, spec in params.items():
            if not isinstance(spec, dict):
                continue

            # Handle nested sections (like timeframes.weights)
            if 'type' not in spec:
                self._parse_section(f"{section}.{name}", spec, prefix=f"{name}.")
                continue

            full_name = f"{prefix}{name}" if prefix else name

            self._params[full_name] = ParameterSpec(
                name=full_name,
                type=spec.get('type', 'float'),
                default=spec.get('default'),
                min=spec.get('min'),
                max=spec.get('max'),
                description=spec.get('description', ''),
                hot_reload=spec.get('hot_reload', True),
                telegram_editable=spec.get('telegram_editable', True),
                category=spec.get('category', section),
            )

    def _load_presets(self, presets: dict):
        """Load preset configurations"""
        for name, preset in presets.items():
            self._presets[name] = {
                'description': preset.get('description', ''),
                'overrides': preset.get('overrides', {}),
            }

    def get(self, name: str, default: Any = None) -> Any:
        """Get parameter value"""
        with self._param_lock:
            if name in self._params:
                return self._params[name].value
            return default

    def get_spec(self, name: str) -> Optional[ParameterSpec]:
        """Get full parameter specification"""
        return self._params.get(name)

    def set(self, name: str, value: Any, modified_by: str = "user") -> bool:
        """
        Set parameter value with validation.

        Returns True if successful, raises ValueError if validation fails.
        """
        with self._param_lock:
            if name not in self._params:
                raise KeyError(f"Unknown parameter: {name}")

            spec = self._params[name]

            # Check if hot-reload is allowed
            if not spec.hot_reload:
                raise ValueError(f"Parameter '{name}' cannot be modified at runtime")

            # Validate
            if not spec.validate(value):
                constraints = []
                if spec.min is not None:
                    constraints.append(f"min={spec.min}")
                if spec.max is not None:
                    constraints.append(f"max={spec.max}")
                raise ValueError(
                    f"Invalid value for {name}: {value}. "
                    f"Type: {spec.type}, Constraints: {', '.join(constraints)}"
                )

            # Coerce and set
            old_value = spec.value
            new_value = spec.coerce(value)
            spec.value = new_value
            spec.last_modified = datetime.now()
            spec.modified_by = modified_by

            # Record change
            self._change_history.append({
                'timestamp': datetime.now().isoformat(),
                'parameter': name,
                'old_value': old_value,
                'new_value': new_value,
                'modified_by': modified_by,
            })

            # Keep only last 100 changes
            if len(self._change_history) > 100:
                self._change_history = self._change_history[-100:]

        # Fire callbacks (outside lock)
        for callback in self._callbacks:
            try:
                callback(name, old_value, new_value)
            except Exception as e:
                logger.error(f"Callback error for {name}: {e}")

        logger.info(f"Parameter '{name}' changed: {old_value} → {new_value} (by {modified_by})")
        return True

    def set_many(self, params: Dict[str, Any], modified_by: str = "user") -> Dict[str, str]:
        """
        Set multiple parameters at once.

        Returns dict of {param_name: error_message} for any failures.
        """
        errors = {}
        for name, value in params.items():
            try:
                self.set(name, value, modified_by)
            except (KeyError, ValueError) as e:
                errors[name] = str(e)
        return errors

    def apply_preset(self, preset_name: str, modified_by: str = "preset") -> bool:
        """Apply a preset configuration"""
        if preset_name not in self._presets:
            raise KeyError(f"Unknown preset: {preset_name}. Available: {list(self._presets.keys())}")

        preset = self._presets[preset_name]
        errors = self.set_many(preset['overrides'], modified_by=f"preset:{preset_name}")

        if errors:
            logger.warning(f"Preset '{preset_name}' applied with errors: {errors}")
        else:
            logger.info(f"Preset '{preset_name}' applied successfully")

        return len(errors) == 0

    def reset(self, name: str) -> bool:
        """Reset parameter to default value"""
        with self._param_lock:
            if name not in self._params:
                raise KeyError(f"Unknown parameter: {name}")
            spec = self._params[name]
            return self.set(name, spec.default, modified_by="reset")

    def reset_all(self):
        """Reset all parameters to defaults"""
        with self._param_lock:
            for name, spec in self._params.items():
                spec.value = spec.default

    def add_callback(self, callback: Callable[[str, Any, Any], None]):
        """
        Register callback for parameter changes.

        Callback signature: callback(param_name, old_value, new_value)
        """
        self._callbacks.append(callback)

    def remove_callback(self, callback: Callable):
        """Remove a registered callback"""
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def get_all(self, category: Optional[str] = None) -> Dict[str, Any]:
        """Get all parameters, optionally filtered by category"""
        with self._param_lock:
            if category:
                return {
                    name: spec.value
                    for name, spec in self._params.items()
                    if spec.category == category
                }
            return {name: spec.value for name, spec in self._params.items()}

    def get_telegram_editable(self) -> Dict[str, ParameterSpec]:
        """Get all parameters that can be edited via Telegram"""
        return {
            name: spec
            for name, spec in self._params.items()
            if spec.telegram_editable
        }

    def get_categories(self) -> List[str]:
        """Get list of all parameter categories"""
        return list(set(spec.category for spec in self._params.values()))

    def get_by_category(self, category: str) -> Dict[str, ParameterSpec]:
        """Get all parameters in a category"""
        return {
            name: spec
            for name, spec in self._params.items()
            if spec.category == category
        }

    def get_presets(self) -> Dict[str, str]:
        """Get available presets with descriptions"""
        return {name: p['description'] for name, p in self._presets.items()}

    def get_change_history(self, limit: int = 20) -> List[Dict]:
        """Get recent change history"""
        return self._change_history[-limit:]

    def export_config(self) -> Dict:
        """Export current configuration as dict"""
        return {
            'version': '3.1.0',
            'exported_at': datetime.now().isoformat(),
            'parameters': {
                name: {
                    'value': spec.value,
                    'default': spec.default,
                    'type': spec.type,
                    'category': spec.category,
                }
                for name, spec in self._params.items()
            }
        }

    def save_config(self, path: Union[str, Path]):
        """Save current configuration to JSON file"""
        path = Path(path)
        with open(path, 'w') as f:
            json.dump(self.export_config(), f, indent=2)
        logger.info(f"Configuration saved to {path}")

    def load_config(self, path: Union[str, Path]):
        """Load configuration from JSON file"""
        path = Path(path)
        with open(path, 'r') as f:
            config = json.load(f)

        if 'parameters' in config:
            for name, data in config['parameters'].items():
                if name in self._params:
                    try:
                        self.set(name, data['value'], modified_by="config_file")
                    except (ValueError, KeyError) as e:
                        logger.warning(f"Could not load {name}: {e}")

    def __repr__(self):
        return f"<ParameterRegistry: {len(self._params)} parameters>"


# Global singleton instance
params = ParameterRegistry()


def get_param(name: str, default: Any = None) -> Any:
    """Convenience function to get parameter"""
    return params.get(name, default)


def set_param(name: str, value: Any) -> bool:
    """Convenience function to set parameter"""
    return params.set(name, value)


# ==============================================================================
# LEGACY COMPATIBILITY LAYER
# ==============================================================================
# These functions provide backward compatibility with the old config.py dicts

def get_position_config() -> Dict:
    """Legacy compatibility: Get POSITION_CONFIG dict"""
    return {
        'account_balance': params.get('account_balance', 10000),
        'risk_per_trade': params.get('risk_per_trade', 0.025),
        'max_concurrent_positions': params.get('max_concurrent_positions', 2),
        'max_position_size_pct': params.get('max_position_size_pct', 0.05),
        'scale_in_enabled': False,
        'scale_in_threshold': 0.3,
    }


def get_entry_criteria() -> Dict:
    """Legacy compatibility: Get ENTRY_CRITERIA dict"""
    return {
        'min_qsci_signal': params.get('min_qsci_signal', 0.12),
        'min_liquidity_adjustment': 0.5,
        'min_dte': params.get('min_dte', 5),
        'max_dte': params.get('max_dte', 21),
        'min_delta': params.get('min_delta', 0.30),
        'max_delta': params.get('max_delta', 0.60),
        'target_moneyness': 1.03,
        'max_spread_pct': 0.02,
        'min_adx': params.get('min_adx', 20),
        'require_trend_alignment': params.get('require_trend_alignment', True),
        'max_iv_rank': params.get('max_iv_rank', 0.6),
        'use_strongest_tf_signal': False,
    }


def get_exit_rules() -> Dict:
    """Legacy compatibility: Get EXIT_RULES dict"""
    return {
        'tp1_target': params.get('tp1_target', 1.5),
        'tp2_target': params.get('tp2_target', 3.0),
        'tp3_target': params.get('tp3_target', 5.0),
        'sl_multiplier': params.get('sl_multiplier', 1.2),
        'roll_dte_threshold': params.get('roll_dte_threshold', 8),
        'mandatory_close_dte': params.get('mandatory_close_dte', 4),
        'trailing_activation': params.get('trailing_activation', 0.8),
        'trailing_distance': params.get('trailing_distance', 0.35),
    }


def get_strategy_params() -> Dict:
    """Legacy compatibility: Get STRATEGY_PARAMS dict"""
    return {
        'only_strong_signals': params.get('only_strong_signals', False),
        'use_sentiment_filter': params.get('use_sentiment_filter', False),
        'use_multi_timeframe': params.get('use_multi_timeframe', True),
        'dynamic_position_sizing': params.get('dynamic_position_sizing', True),
        'use_kelly_criterion': params.get('use_kelly_criterion', False),
        'kelly_fraction': params.get('kelly_fraction', 0.15),
        'multitf_threshold': 0.12,
        'sentiment_filter_threshold': 0.05,
        'require_volume_confirmation': params.get('require_volume_confirmation', False),
        'min_win_probability': 0.40,
    }


def get_qsci_config() -> Dict:
    """Legacy compatibility: Get QSCI_CONFIG dict"""
    return {
        'timeframe_weights': {
            '4h': params.get('4h', 0.25),
            '2h': params.get('2h', 0.20),
            '1h': params.get('1h', 0.15),
            '30m': params.get('30m', 0.15),
            '15m': params.get('15m', 0.10),
            '5m': params.get('5m', 0.10),
            '1m': params.get('1m', 0.05),
        },
        'rsi_period': params.get('rsi_period', 14),
        'macd_fast': params.get('macd_fast', 12),
        'macd_slow': params.get('macd_slow', 26),
        'macd_signal': params.get('macd_signal', 9),
        'atr_period': params.get('atr_period', 14),
        'bb_period': params.get('bb_period', 20),
        'bb_std': params.get('bb_std', 2.0),
        'adx_period': params.get('adx_period', 14),
        'momentum_weight': params.get('momentum_weight', 0.35),
        'trend_weight': params.get('trend_weight', 0.30),
        'volume_weight': params.get('volume_weight', 0.15),
        'volatility_weight': params.get('volatility_weight', 0.10),
        'pattern_weight': params.get('pattern_weight', 0.10),
        'mtc_weight': params.get('mtc_weight', 0.70),
        'sentiment_weight': params.get('sentiment_weight', 0.30),
    }


if __name__ == "__main__":
    # Test the registry
    print("Testing ParameterRegistry...")

    registry = ParameterRegistry()
    print(f"Loaded {len(registry._params)} parameters")

    # Test get
    print(f"\nmin_qsci_signal = {registry.get('min_qsci_signal')}")

    # Test set
    print("\nSetting min_qsci_signal to 0.15...")
    registry.set('min_qsci_signal', 0.15)
    print(f"min_qsci_signal = {registry.get('min_qsci_signal')}")

    # Test validation
    print("\nTesting validation (should fail)...")
    try:
        registry.set('min_qsci_signal', 2.0)  # Out of range
    except ValueError as e:
        print(f"Validation error: {e}")

    # Test presets
    print(f"\nAvailable presets: {registry.get_presets()}")

    # Test categories
    print(f"\nCategories: {registry.get_categories()}")

    # Test Telegram editable
    print(f"\nTelegram editable params: {len(registry.get_telegram_editable())}")

    print("\n✅ All tests passed!")
