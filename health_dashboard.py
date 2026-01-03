"""
QSCI Health Check Dashboard

Features:
- System health monitoring
- Latency tracking
- Performance metrics
- HTTP health check endpoint
- Telegram health reports

Author: QSCI Trading System
Version: 3.1.0
"""

import os
import sys
import time
import json
import logging
import threading
import socket
import psutil
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field, asdict
from collections import deque
from http.server import HTTPServer, BaseHTTPRequestHandler

logger = logging.getLogger(__name__)


# ==============================================================================
# HEALTH CHECK DATA STRUCTURES
# ==============================================================================

@dataclass
class SystemMetrics:
    """System resource metrics"""
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    memory_used_mb: float = 0.0
    memory_available_mb: float = 0.0
    disk_percent: float = 0.0
    network_sent_mb: float = 0.0
    network_recv_mb: float = 0.0
    python_memory_mb: float = 0.0
    thread_count: int = 0
    open_files: int = 0
    timestamp: float = field(default_factory=time.time)


@dataclass
class ComponentHealth:
    """Health status of a system component"""
    name: str
    status: str = "unknown"  # healthy, degraded, unhealthy, unknown
    last_check: float = 0.0
    response_time_ms: float = 0.0
    error_count: int = 0
    last_error: str = ""
    details: Dict = field(default_factory=dict)

    @property
    def is_healthy(self) -> bool:
        return self.status == "healthy"


@dataclass
class TradingMetrics:
    """Trading-specific metrics"""
    account_balance: float = 0.0
    total_pnl: float = 0.0
    daily_pnl: float = 0.0
    open_positions: int = 0
    total_trades: int = 0
    win_rate: float = 0.0
    max_drawdown: float = 0.0
    last_trade_time: Optional[float] = None
    is_trading_paused: bool = False
    signals_generated: int = 0
    trades_executed: int = 0


@dataclass
class LatencyMetrics:
    """Latency tracking"""
    tick_to_signal_avg_ms: float = 0.0
    tick_to_signal_p95_ms: float = 0.0
    signal_to_trade_avg_ms: float = 0.0
    signal_to_trade_p95_ms: float = 0.0
    websocket_latency_avg_ms: float = 0.0
    websocket_latency_max_ms: float = 0.0
    telegram_latency_avg_ms: float = 0.0
    database_latency_avg_ms: float = 0.0


@dataclass
class HealthReport:
    """Complete system health report"""
    timestamp: str
    overall_status: str  # healthy, degraded, unhealthy
    uptime_seconds: float
    system: SystemMetrics
    components: Dict[str, ComponentHealth]
    trading: TradingMetrics
    latency: LatencyMetrics
    alerts: List[str] = field(default_factory=list)
    version: str = "3.1.0"


# ==============================================================================
# HEALTH MONITOR
# ==============================================================================

class HealthMonitor:
    """
    Central health monitoring system

    Features:
    - System resource monitoring
    - Component health checks
    - Latency tracking
    - Alert generation
    - HTTP endpoint for external monitoring
    """

    def __init__(
        self,
        check_interval: int = 30,  # seconds between health checks
        alert_callback: Optional[Callable[[str], None]] = None,
    ):
        self.check_interval = check_interval
        self.alert_callback = alert_callback
        self.start_time = time.time()

        # Component health
        self._components: Dict[str, ComponentHealth] = {}

        # Latency tracking
        self._latency_samples: Dict[str, deque] = {}

        # Metrics history
        self._system_history: deque = deque(maxlen=360)  # 3 hours at 30s interval

        # Alerts
        self._active_alerts: List[str] = []
        self._alert_history: deque = deque(maxlen=100)

        # Trading metrics (updated externally)
        self.trading_metrics = TradingMetrics()

        # Monitoring thread
        self._monitor_thread: Optional[threading.Thread] = None
        self._running = False

        # Initialize components
        self._init_components()

    def _init_components(self):
        """Initialize default components to monitor"""
        default_components = [
            "binance_rest",
            "binance_websocket",
            "telegram",
            "mongodb",
            "qsci_engine",
            "options_pricer",
        ]
        for name in default_components:
            self._components[name] = ComponentHealth(name=name)
            self._latency_samples[name] = deque(maxlen=100)

    def start(self):
        """Start background health monitoring"""
        if self._running:
            return

        self._running = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        logger.info("✓ Health monitor started")

    def stop(self):
        """Stop health monitoring"""
        self._running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
        logger.info("Health monitor stopped")

    def _monitor_loop(self):
        """Background monitoring loop"""
        while self._running:
            try:
                self._collect_system_metrics()
                self._check_alerts()
            except Exception as e:
                logger.error(f"Health monitor error: {e}")

            time.sleep(self.check_interval)

    def _collect_system_metrics(self) -> SystemMetrics:
        """Collect current system metrics"""
        try:
            process = psutil.Process()

            metrics = SystemMetrics(
                cpu_percent=psutil.cpu_percent(interval=None),
                memory_percent=psutil.virtual_memory().percent,
                memory_used_mb=psutil.virtual_memory().used / (1024 * 1024),
                memory_available_mb=psutil.virtual_memory().available / (1024 * 1024),
                disk_percent=psutil.disk_usage('/').percent,
                network_sent_mb=psutil.net_io_counters().bytes_sent / (1024 * 1024),
                network_recv_mb=psutil.net_io_counters().bytes_recv / (1024 * 1024),
                python_memory_mb=process.memory_info().rss / (1024 * 1024),
                thread_count=threading.active_count(),
                open_files=len(process.open_files()) if hasattr(process, 'open_files') else 0,
                timestamp=time.time(),
            )

            self._system_history.append(metrics)
            return metrics

        except Exception as e:
            logger.error(f"Failed to collect system metrics: {e}")
            return SystemMetrics()

    def _check_alerts(self):
        """Check for alert conditions"""
        new_alerts = []

        # System alerts
        if self._system_history:
            latest = self._system_history[-1]

            if latest.cpu_percent > 90:
                new_alerts.append(f"🔴 High CPU: {latest.cpu_percent:.1f}%")

            if latest.memory_percent > 85:
                new_alerts.append(f"🔴 High Memory: {latest.memory_percent:.1f}%")

            if latest.disk_percent > 90:
                new_alerts.append(f"🟡 Disk Near Full: {latest.disk_percent:.1f}%")

            if latest.python_memory_mb > 2000:  # 2GB
                new_alerts.append(f"🟡 High Python Memory: {latest.python_memory_mb:.0f}MB")

        # Component alerts
        for name, component in self._components.items():
            if component.status == "unhealthy":
                new_alerts.append(f"🔴 Component unhealthy: {name}")
            elif component.status == "degraded":
                new_alerts.append(f"🟡 Component degraded: {name}")

            if component.error_count > 5:
                new_alerts.append(f"🟡 High error count for {name}: {component.error_count}")

        # Trading alerts
        if self.trading_metrics.max_drawdown > 0.15:
            new_alerts.append(f"🔴 High drawdown: {self.trading_metrics.max_drawdown:.1%}")

        if self.trading_metrics.is_trading_paused:
            new_alerts.append("🟡 Trading is paused")

        # Notify about new alerts
        for alert in new_alerts:
            if alert not in self._active_alerts:
                self._active_alerts.append(alert)
                self._alert_history.append({
                    "time": datetime.now().isoformat(),
                    "message": alert
                })

                if self.alert_callback:
                    try:
                        self.alert_callback(alert)
                    except Exception as e:
                        logger.error(f"Alert callback error: {e}")

        # Remove resolved alerts
        self._active_alerts = [a for a in self._active_alerts if a in new_alerts]

    def record_component_check(
        self,
        name: str,
        is_healthy: bool,
        response_time_ms: float = 0.0,
        error: str = "",
        details: Dict = None,
    ):
        """Record a component health check result"""
        if name not in self._components:
            self._components[name] = ComponentHealth(name=name)

        component = self._components[name]
        component.last_check = time.time()
        component.response_time_ms = response_time_ms

        if is_healthy:
            component.status = "healthy"
            component.error_count = max(0, component.error_count - 1)
        else:
            component.error_count += 1
            component.last_error = error

            if component.error_count >= 3:
                component.status = "unhealthy"
            else:
                component.status = "degraded"

        if details:
            component.details = details

        # Track latency
        if name in self._latency_samples:
            self._latency_samples[name].append(response_time_ms)

    def record_latency(self, category: str, latency_ms: float):
        """Record a latency sample"""
        if category not in self._latency_samples:
            self._latency_samples[category] = deque(maxlen=100)
        self._latency_samples[category].append(latency_ms)

    def update_trading_metrics(
        self,
        account_balance: float = None,
        total_pnl: float = None,
        daily_pnl: float = None,
        open_positions: int = None,
        total_trades: int = None,
        win_rate: float = None,
        max_drawdown: float = None,
        is_paused: bool = None,
    ):
        """Update trading metrics"""
        if account_balance is not None:
            self.trading_metrics.account_balance = account_balance
        if total_pnl is not None:
            self.trading_metrics.total_pnl = total_pnl
        if daily_pnl is not None:
            self.trading_metrics.daily_pnl = daily_pnl
        if open_positions is not None:
            self.trading_metrics.open_positions = open_positions
        if total_trades is not None:
            self.trading_metrics.total_trades = total_trades
        if win_rate is not None:
            self.trading_metrics.win_rate = win_rate
        if max_drawdown is not None:
            self.trading_metrics.max_drawdown = max_drawdown
        if is_paused is not None:
            self.trading_metrics.is_trading_paused = is_paused

    def _calculate_latency_metrics(self) -> LatencyMetrics:
        """Calculate aggregated latency metrics"""
        def calc_stats(samples: deque) -> tuple:
            if not samples:
                return 0.0, 0.0
            data = list(samples)
            avg = sum(data) / len(data)
            p95 = sorted(data)[int(len(data) * 0.95)] if len(data) >= 20 else max(data)
            return avg, p95

        tick_avg, tick_p95 = calc_stats(self._latency_samples.get("tick_to_signal", deque()))
        signal_avg, signal_p95 = calc_stats(self._latency_samples.get("signal_to_trade", deque()))
        ws_samples = self._latency_samples.get("websocket", deque())
        ws_avg, ws_p95 = calc_stats(ws_samples)
        tele_avg, _ = calc_stats(self._latency_samples.get("telegram", deque()))
        db_avg, _ = calc_stats(self._latency_samples.get("mongodb", deque()))

        return LatencyMetrics(
            tick_to_signal_avg_ms=tick_avg,
            tick_to_signal_p95_ms=tick_p95,
            signal_to_trade_avg_ms=signal_avg,
            signal_to_trade_p95_ms=signal_p95,
            websocket_latency_avg_ms=ws_avg,
            websocket_latency_max_ms=max(ws_samples) if ws_samples else 0,
            telegram_latency_avg_ms=tele_avg,
            database_latency_avg_ms=db_avg,
        )

    def get_overall_status(self) -> str:
        """Determine overall system status"""
        unhealthy_count = sum(1 for c in self._components.values() if c.status == "unhealthy")
        degraded_count = sum(1 for c in self._components.values() if c.status == "degraded")

        if unhealthy_count > 0 or len(self._active_alerts) > 3:
            return "unhealthy"
        elif degraded_count > 0 or len(self._active_alerts) > 0:
            return "degraded"
        return "healthy"

    def get_health_report(self) -> HealthReport:
        """Generate complete health report"""
        system_metrics = self._system_history[-1] if self._system_history else SystemMetrics()

        return HealthReport(
            timestamp=datetime.now().isoformat(),
            overall_status=self.get_overall_status(),
            uptime_seconds=time.time() - self.start_time,
            system=system_metrics,
            components={name: comp for name, comp in self._components.items()},
            trading=self.trading_metrics,
            latency=self._calculate_latency_metrics(),
            alerts=self._active_alerts.copy(),
            version="3.1.0",
        )

    def get_json_report(self) -> str:
        """Get health report as JSON string"""
        report = self.get_health_report()

        # Convert to dict
        report_dict = {
            "timestamp": report.timestamp,
            "overall_status": report.overall_status,
            "uptime_seconds": report.uptime_seconds,
            "uptime_human": str(timedelta(seconds=int(report.uptime_seconds))),
            "version": report.version,
            "alerts": report.alerts,
            "system": asdict(report.system),
            "components": {
                name: {
                    "status": comp.status,
                    "response_time_ms": comp.response_time_ms,
                    "error_count": comp.error_count,
                    "last_error": comp.last_error,
                }
                for name, comp in report.components.items()
            },
            "trading": asdict(report.trading),
            "latency": asdict(report.latency),
        }

        return json.dumps(report_dict, indent=2)

    def get_telegram_summary(self) -> str:
        """Generate health summary for Telegram"""
        report = self.get_health_report()

        status_emoji = {
            "healthy": "🟢",
            "degraded": "🟡",
            "unhealthy": "🔴",
        }

        uptime = timedelta(seconds=int(report.uptime_seconds))

        text = f"""
{status_emoji.get(report.overall_status, '⚪')} <b>System Health: {report.overall_status.upper()}</b>
━━━━━━━━━━━━━━━━━━━━━━━━━

⏱️ <b>Uptime:</b> {uptime}

💻 <b>System:</b>
• CPU: {report.system.cpu_percent:.1f}%
• Memory: {report.system.memory_percent:.1f}%
• Python Mem: {report.system.python_memory_mb:.0f}MB
• Threads: {report.system.thread_count}

📊 <b>Trading:</b>
• Balance: ${report.trading.account_balance:,.2f}
• P&L: ${report.trading.total_pnl:+,.2f}
• Positions: {report.trading.open_positions}
• Win Rate: {report.trading.win_rate:.1%}

⚡ <b>Latency:</b>
• Tick→Signal: {report.latency.tick_to_signal_avg_ms:.1f}ms
• WebSocket: {report.latency.websocket_latency_avg_ms:.1f}ms

🔌 <b>Components:</b>
"""
        for name, comp in report.components.items():
            emoji = status_emoji.get(comp.status, "⚪")
            text += f"• {emoji} {name}: {comp.response_time_ms:.1f}ms\n"

        if report.alerts:
            text += "\n⚠️ <b>Alerts:</b>\n"
            for alert in report.alerts[:5]:
                text += f"• {alert}\n"

        return text.strip()


# ==============================================================================
# HTTP HEALTH CHECK SERVER
# ==============================================================================

class HealthCheckHandler(BaseHTTPRequestHandler):
    """HTTP handler for health check endpoint"""

    monitor: Optional[HealthMonitor] = None

    def log_message(self, format, *args):
        """Suppress default logging"""
        pass

    def do_GET(self):
        """Handle GET requests"""
        if self.path == "/health" or self.path == "/":
            self._send_health()
        elif self.path == "/health/live":
            self._send_liveness()
        elif self.path == "/health/ready":
            self._send_readiness()
        elif self.path == "/metrics":
            self._send_metrics()
        else:
            self.send_error(404)

    def _send_health(self):
        """Send full health check response"""
        if self.monitor:
            report = self.monitor.get_json_report()
            status = self.monitor.get_overall_status()

            code = 200 if status == "healthy" else 503 if status == "unhealthy" else 200

            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("X-Health-Status", status)
            self.end_headers()
            self.wfile.write(report.encode())
        else:
            self.send_error(503, "Monitor not initialized")

    def _send_liveness(self):
        """Send simple liveness probe response"""
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK")

    def _send_readiness(self):
        """Send readiness probe response"""
        if self.monitor:
            status = self.monitor.get_overall_status()
            code = 200 if status != "unhealthy" else 503

            self.send_response(code)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(status.encode())
        else:
            self.send_error(503, "Not ready")

    def _send_metrics(self):
        """Send Prometheus-style metrics"""
        if self.monitor:
            report = self.monitor.get_health_report()

            metrics = []
            metrics.append(f'# HELP qsci_uptime_seconds System uptime in seconds')
            metrics.append(f'# TYPE qsci_uptime_seconds gauge')
            metrics.append(f'qsci_uptime_seconds {report.uptime_seconds:.0f}')

            metrics.append(f'# HELP qsci_cpu_percent CPU usage percentage')
            metrics.append(f'# TYPE qsci_cpu_percent gauge')
            metrics.append(f'qsci_cpu_percent {report.system.cpu_percent}')

            metrics.append(f'# HELP qsci_memory_percent Memory usage percentage')
            metrics.append(f'# TYPE qsci_memory_percent gauge')
            metrics.append(f'qsci_memory_percent {report.system.memory_percent}')

            metrics.append(f'# HELP qsci_account_balance Account balance in USD')
            metrics.append(f'# TYPE qsci_account_balance gauge')
            metrics.append(f'qsci_account_balance {report.trading.account_balance}')

            metrics.append(f'# HELP qsci_total_pnl Total P&L in USD')
            metrics.append(f'# TYPE qsci_total_pnl gauge')
            metrics.append(f'qsci_total_pnl {report.trading.total_pnl}')

            metrics.append(f'# HELP qsci_open_positions Number of open positions')
            metrics.append(f'# TYPE qsci_open_positions gauge')
            metrics.append(f'qsci_open_positions {report.trading.open_positions}')

            metrics.append(f'# HELP qsci_latency_tick_to_signal_ms Tick to signal latency')
            metrics.append(f'# TYPE qsci_latency_tick_to_signal_ms gauge')
            metrics.append(f'qsci_latency_tick_to_signal_ms {report.latency.tick_to_signal_avg_ms}')

            for name, comp in report.components.items():
                status_val = 1 if comp.status == "healthy" else 0.5 if comp.status == "degraded" else 0
                metrics.append(f'qsci_component_status{{component="{name}"}} {status_val}')

            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write("\n".join(metrics).encode())
        else:
            self.send_error(503)


class HealthCheckServer:
    """
    HTTP server for health check endpoints

    Endpoints:
    - GET /health - Full health report (JSON)
    - GET /health/live - Kubernetes liveness probe
    - GET /health/ready - Kubernetes readiness probe
    - GET /metrics - Prometheus metrics
    """

    def __init__(
        self,
        monitor: HealthMonitor,
        host: str = "0.0.0.0",
        port: int = 8080,
    ):
        self.monitor = monitor
        self.host = host
        self.port = port
        self._server: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    def start(self):
        """Start the health check server"""
        HealthCheckHandler.monitor = self.monitor

        self._server = HTTPServer((self.host, self.port), HealthCheckHandler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

        logger.info(f"✓ Health check server started on http://{self.host}:{self.port}")

    def stop(self):
        """Stop the health check server"""
        if self._server:
            self._server.shutdown()
        logger.info("Health check server stopped")


# ==============================================================================
# INTEGRATION WITH LIVE TRADER
# ==============================================================================

def integrate_with_trader(trader, monitor: HealthMonitor):
    """
    Integrate health monitoring with the live trader

    Call this from qsci_live_trader.py to enable monitoring.
    """
    def update_metrics():
        """Update trading metrics from trader state"""
        monitor.update_trading_metrics(
            account_balance=getattr(trader, 'account_balance', 0),
            total_pnl=getattr(trader, 'total_pnl', 0),
            daily_pnl=getattr(trader, 'daily_pnl', 0),
            open_positions=len([p for p in getattr(trader, 'positions', []) if p.status == "OPEN"]),
            total_trades=len(getattr(trader, 'trades_log', [])),
            is_paused=getattr(trader, 'is_paused', False),
        )

        # Calculate win rate
        trades = getattr(trader, 'trades_log', [])
        if trades:
            wins = sum(1 for t in trades if t.get('pnl_after_fees', 0) > 0)
            monitor.update_trading_metrics(win_rate=wins / len(trades))

    # Register update callback
    return update_metrics


# ==============================================================================
# TEST
# ==============================================================================

if __name__ == "__main__":
    print("Testing Health Check Dashboard...\n")

    # Create monitor
    monitor = HealthMonitor(check_interval=5)
    monitor.start()

    # Simulate component checks
    monitor.record_component_check("binance_rest", True, response_time_ms=45.2)
    monitor.record_component_check("binance_websocket", True, response_time_ms=12.5)
    monitor.record_component_check("telegram", True, response_time_ms=180.3)
    monitor.record_component_check("mongodb", False, response_time_ms=0, error="Connection timeout")

    # Update trading metrics
    monitor.update_trading_metrics(
        account_balance=10500,
        total_pnl=500,
        daily_pnl=75,
        open_positions=2,
        total_trades=15,
        win_rate=0.67,
        max_drawdown=0.08,
    )

    # Record some latency samples
    for i in range(20):
        monitor.record_latency("tick_to_signal", 2.5 + i * 0.1)
        monitor.record_latency("websocket", 15 + i * 0.5)

    # Wait for metrics collection
    time.sleep(2)

    # Get report
    print("Health Report (JSON):")
    print(monitor.get_json_report())

    print("\n" + "="*50)
    print("\nHealth Report (Telegram):")
    print(monitor.get_telegram_summary())

    # Start HTTP server
    print("\n" + "="*50)
    print("\nStarting HTTP health server on :8080...")
    server = HealthCheckServer(monitor, port=8080)

    try:
        server.start()
        print("Server running. Press Ctrl+C to stop.")
        print("Try: curl http://localhost:8080/health")

        # Keep running for demo
        time.sleep(5)
    except KeyboardInterrupt:
        pass
    finally:
        server.stop()
        monitor.stop()

    print("\n✅ Health check dashboard test complete!")
