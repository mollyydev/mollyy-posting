from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from data.config import DATABASE_URL

# We can use SQLAlchemyJobStore or just memory if we rely on our DB for metadata.
# Since we have `ScheduledPost` in our DB, we can use MemoryJobStore and reload on restart,
# OR use SQLAlchemyJobStore to persist jobs directly. 
# Using Memory for simplicity + reload logic is safer if we want full control, 
# but SQLAlchemyJobStore is more robust.
# Let's use Memory for now and rely on "ScheduledPost" table to re-populate on startup if needed (advanced),
# or just keep it simple. User requested "SQLite" so we can persist jobs there too.

# Note: sqlite url for apscheduler might need adjustment.
jobstores = {
    'default': SQLAlchemyJobStore(url=DATABASE_URL.replace("+aiosqlite", "")) 
}

scheduler = AsyncIOScheduler(jobstores=jobstores, timezone="UTC")

async def start_scheduler():
    scheduler.start()
    print("Scheduler started!")