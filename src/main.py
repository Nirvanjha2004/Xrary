import signal
import sys
import time

import structlog
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from src.agents.hiring_agent import HiringAgent
from src.config import Settings
from src.storage.database import init_db


# Configure structlog
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


def run_agent_cycle(settings: Settings) -> None:
    """
    Run a single hiring agent cycle.
    
    Args:
        settings: Application settings
    """
    try:
        logger.info("hiring_agent_cycle_start", poll_interval_minutes=settings.poll_interval_minutes)
        agent = HiringAgent(settings)
        state = agent.run_once()
        
        logger.info(
            "hiring_agent_cycle_complete",
            notifications_sent=state.get("notifications_sent", 0),
            error_count=state.get("error_count", 0),
            last_run=state.get("last_run"),
        )
    except Exception as e:
        logger.error(
            "hiring_agent_cycle_failed",
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True,
        )


def main() -> None:
    """
    Main entry point. Initializes the database and starts the scheduler.
    """
    logger.info("initializing_hiring_agent_service")
    
    # Initialize database
    init_db()
    logger.info("database_initialized")
    
    # Load settings
    settings = Settings
    logger.info("settings_loaded", poll_interval_minutes=settings.poll_interval_minutes)
    
    # Create scheduler
    scheduler = BackgroundScheduler()
    
    # Add the job to run the agent cycle at the configured interval
    scheduler.add_job(
        run_agent_cycle,
        trigger=IntervalTrigger(minutes=settings.poll_interval_minutes),
        id="hiring_poll",
        replace_existing=True,
        args=[settings],
    )
    logger.info("scheduler_job_added", job_id="hiring_poll", interval_minutes=settings.poll_interval_minutes)
    
    # Register signal handlers for graceful shutdown
    def handle_shutdown(signum, frame):
        logger.info("shutdown_signal_received", signal=signal.Signals(signum).name)
        scheduler.shutdown(wait=True)
        logger.info("scheduler_shutdown_complete")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)
    logger.info("signal_handlers_registered")
    
    # Start the scheduler
    scheduler.start()
    logger.info("scheduler_started")
    
    # Block the main thread while the scheduler is running
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("keyboard_interrupt_received")
        scheduler.shutdown(wait=True)
        logger.info("scheduler_shutdown_on_interrupt")
        sys.exit(0)


if __name__ == "__main__":
    main()
