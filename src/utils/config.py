"""Configuration management"""
import yaml
from pathlib import Path
from typing import Any, Dict
import multiprocessing

try:
    import torch
except Exception:  # torch might not be available in some contexts
    torch = None


class Config:
    """Configuration manager"""
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = Path(config_path)
        self._config = self._load_config()
        # Optionally auto-optimize some settings based on hardware
        self._auto_optimize_if_enabled()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value using dot notation"""
        keys = key.split('.')
        value = self._config
        
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
            
            if value is None:
                return default
        
        return value
    
    def set(self, key: str, value: Any):
        """Set configuration value using dot notation"""
        keys = key.split('.')
        config = self._config
        
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        config[keys[-1]] = value
    
    def save(self):
        """Save configuration to file"""
        with open(self.config_path, 'w', encoding='utf-8') as f:
            yaml.dump(self._config, f, default_flow_style=False, allow_unicode=True)
    
    @property
    def all(self) -> Dict[str, Any]:
        """Get all configuration"""
        return self._config

    # ------------------------------------------------------------------
    # Auto-optimization helpers
    # ------------------------------------------------------------------
    def _auto_optimize_if_enabled(self):
        """Auto-tune a few config values based on detected hardware.

        Controlled by config key `auto_optimize_on_start` (default: True).
        This is applied in-memory on load and does not overwrite the YAML
        file unless `save()` is called explicitly.
        """
        enabled = self.get('auto_optimize_on_start', True)
        if not enabled:
            return

        # Detect CPU cores
        try:
            num_cores = multiprocessing.cpu_count()
        except Exception:
            num_cores = 4

        # Detect CUDA GPU (Nvidia) if torch is available
        has_cuda = bool(torch and torch.cuda.is_available())

        if has_cuda:
            # Profile: Nvidia GPU (e.g. i7 + RTX 3080 Ti)
            self.set('gpu.enabled', True)
            # Batch size tuned for 10–12GB+ VRAM; can be adjusted manually later
            self.set('gpu.batch_size', self.get('gpu.batch_size', 32))
            self.set('gpu.fp16', self.get('gpu.fp16', True))

            # Download: more parallelism is fine when GPU handles heavy work
            self.set('download.max_parallel', self.get('download.max_parallel', 8))
            self.set('download.video_quality', self.get('download.video_quality', '480p'))

            # Processing threads for Code groups
            default_workers = min(8, max(1, num_cores // 2))
            self.set('processing.max_code_group_workers', self.get('processing.max_code_group_workers', default_workers))
        else:
            # Profile: CPU-only (e.g. 5950X + RX 6800 XT on Windows)
            self.set('gpu.enabled', False)

            # Fewer parallel downloads to avoid overloading CPU & disk
            self.set('download.max_parallel', self.get('download.max_parallel', 6))
            # Lower quality is sufficient for CLIP at 224x224 input
            self.set('download.video_quality', self.get('download.video_quality', '360p'))

            default_workers = min(12, max(1, num_cores - 2))
            self.set('processing.max_code_group_workers', self.get('processing.max_code_group_workers', default_workers))


# Global config instance
_config = None


def get_config(config_path: str = "config.yaml") -> Config:
    """Get global config instance"""
    global _config
    if _config is None:
        _config = Config(config_path)
    return _config

