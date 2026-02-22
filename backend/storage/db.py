"""
Database Module
SQLite storage with async operations for selector history and scrape logs.
"""

import aiosqlite
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any
from loguru import logger
import json


class Database:
    """
    Async SQLite database manager.
    
    Tables:
    - selector_history: Tracks selector changes over time
    - scrape_jobs: Logs of scraping jobs
    - healing_logs: Self-healing attempts and results
    - training_data: Labeled data for ML model
    """

    def __init__(self, db_path: str = "data/scraper.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection: Optional[aiosqlite.Connection] = None

    async def connect(self) -> None:
        """Establish database connection."""
        self._connection = await aiosqlite.connect(str(self.db_path))
        self._connection.row_factory = aiosqlite.Row
        await self._create_tables()
        logger.info(f"Database connected: {self.db_path}")

    async def disconnect(self) -> None:
        """Close database connection."""
        if self._connection:
            await self._connection.close()
            logger.info("Database disconnected")

    async def _create_tables(self) -> None:
        """Create database tables if they don't exist."""
        await self._connection.executescript("""
            -- Selector history for tracking changes
            CREATE TABLE IF NOT EXISTS selector_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL,
                original_selector TEXT NOT NULL,
                current_selector TEXT NOT NULL,
                element_info TEXT,  -- JSON string of element attributes
                success BOOLEAN NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            -- Scrape job logs
            CREATE TABLE IF NOT EXISTS scrape_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT UNIQUE NOT NULL,
                url TEXT NOT NULL,
                selectors TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                result TEXT,
                error_message TEXT,
                healing_triggered BOOLEAN DEFAULT FALSE,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            -- Self-healing attempt logs
            CREATE TABLE IF NOT EXISTS healing_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT,
                original_selector TEXT NOT NULL,
                new_selector TEXT,
                success BOOLEAN NOT NULL,
                confidence REAL,
                candidates_analyzed INTEGER,
                strategy_used TEXT,
                healing_time_ms REAL,
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (job_id) REFERENCES scrape_jobs(job_id)
            );
            
            -- Training data for ML model
            CREATE TABLE IF NOT EXISTS training_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                features TEXT NOT NULL,
                label INTEGER NOT NULL,
                source TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            -- Settings table (single row)
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                api_url TEXT DEFAULT 'http://localhost:8000',
                timeout INTEGER DEFAULT 15,
                headless BOOLEAN DEFAULT TRUE,
                confidence_threshold REAL DEFAULT 0.6,
                max_candidates INTEGER DEFAULT 100,
                retention_days INTEGER DEFAULT 30,
                auto_retrain BOOLEAN DEFAULT FALSE,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            -- Initialize default settings if not exists
            INSERT OR IGNORE INTO settings (id) VALUES (1);
            
            -- Product scrape sessions
            CREATE TABLE IF NOT EXISTS scrape_sessions (
                id TEXT PRIMARY KEY,
                domain TEXT NOT NULL,
                url TEXT NOT NULL,
                session_name TEXT NOT NULL,
                container_xpath TEXT NOT NULL,
                product_count INTEGER DEFAULT 0,
                products TEXT DEFAULT '[]',
                execution_time_ms REAL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            -- Create indexes
            CREATE INDEX IF NOT EXISTS idx_selector_history_url 
                ON selector_history(url);
            CREATE INDEX IF NOT EXISTS idx_scrape_jobs_status 
                ON scrape_jobs(status);
            CREATE INDEX IF NOT EXISTS idx_healing_logs_job 
                ON healing_logs(job_id);
            CREATE INDEX IF NOT EXISTS idx_scrape_sessions_domain
                ON scrape_sessions(domain);
        """)
        
        # Migration: Add element_info column if not exists
        try:
            await self._connection.execute("ALTER TABLE selector_history ADD COLUMN element_info TEXT")
        except Exception:
            pass
            
        # Migration: Add current_selector column if not exists
        try:
            await self._connection.execute("ALTER TABLE selector_history ADD COLUMN current_selector TEXT DEFAULT ''")
            # Update existing rows to have current_selector = original_selector
            await self._connection.execute("UPDATE selector_history SET current_selector = original_selector WHERE current_selector = ''")
        except Exception:
            pass

        # Migration: Add success column if not exists
        try:
            await self._connection.execute("ALTER TABLE selector_history ADD COLUMN success BOOLEAN DEFAULT 1")
        except Exception:
            pass
            
        await self._connection.commit()

    async def get_settings(self) -> Dict[str, Any]:
        """Get application settings."""
        cursor = await self._connection.execute(
            "SELECT * FROM settings WHERE id = 1"
        )
        row = await cursor.fetchone()
        return dict(row) if row else {}

    async def update_settings(self, settings: Dict[str, Any]) -> None:
        """Update application settings."""
        await self._connection.execute(
            """
            UPDATE settings 
            SET api_url = ?, timeout = ?, headless = ?, 
                confidence_threshold = ?, max_candidates = ?, 
                retention_days = ?, auto_retrain = ?, updated_at = ?
            WHERE id = 1
            """,
            (
                settings.get("api_url"),
                settings.get("timeout"),
                settings.get("headless"),
                settings.get("confidence_threshold"),
                settings.get("max_candidates"),
                settings.get("retention_days"),
                settings.get("auto_retrain"),
                datetime.utcnow()
            )
        )
        await self._connection.commit()

    async def insert_selector_history(
        self,
        url: str,
        original_selector: str,
        new_selector: Optional[str] = None,
        element_snapshot: Optional[Dict] = None,
        confidence: Optional[float] = None,
        strategy: Optional[str] = None
    ) -> int:
        """Insert new selector history record."""
        cursor = await self._connection.execute(
            """
            INSERT INTO selector_history 
            (url, original_selector, new_selector, element_snapshot, confidence, strategy)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                url,
                original_selector,
                new_selector,
                json.dumps(element_snapshot) if element_snapshot else None,
                confidence,
                strategy
            )
        )
        await self._connection.commit()
        return cursor.lastrowid

    async def get_selector_history(
        self,
        url: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get selector history, optionally filtered by URL."""
        if url:
            cursor = await self._connection.execute(
                """
                SELECT * FROM selector_history 
                WHERE url = ? 
                ORDER BY created_at DESC 
                LIMIT ?
                """,
                (url, limit)
            )
        else:
            cursor = await self._connection.execute(
                """
                SELECT * FROM selector_history 
                ORDER BY created_at DESC 
                LIMIT ?
                """,
                (limit,)
            )
        
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def insert_scrape_job(
        self,
        job_id: str,
        url: str,
        selectors: List[str]
    ) -> None:
        """Insert new scrape job."""
        await self._connection.execute(
            """
            INSERT INTO scrape_jobs (job_id, url, selectors, status, started_at)
            VALUES (?, ?, ?, 'running', ?)
            """,
            (job_id, url, json.dumps(selectors), datetime.utcnow())
        )
        await self._connection.commit()

    async def update_scrape_job(
        self,
        job_id: str,
        status: str,
        result: Optional[Dict] = None,
        error_message: Optional[str] = None,
        healing_triggered: bool = False
    ) -> None:
        """Update scrape job status."""
        await self._connection.execute(
            """
            UPDATE scrape_jobs 
            SET status = ?, result = ?, error_message = ?, 
                healing_triggered = ?, completed_at = ?
            WHERE job_id = ?
            """,
            (
                status,
                json.dumps(result) if result else None,
                error_message,
                healing_triggered,
                datetime.utcnow(),
                job_id
            )
        )
        await self._connection.commit()

    async def get_scrape_jobs(
        self,
        status: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get scrape jobs, optionally filtered by status."""
        if status:
            cursor = await self._connection.execute(
                """
                SELECT * FROM scrape_jobs 
                WHERE status = ? 
                ORDER BY created_at DESC 
                LIMIT ?
                """,
                (status, limit)
            )
        else:
            cursor = await self._connection.execute(
                """
                SELECT * FROM scrape_jobs 
                ORDER BY created_at DESC 
                LIMIT ?
                """,
                (limit,)
            )
        
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def insert_healing_log(
        self,
        original_selector: str,
        new_selector: Optional[str],
        success: bool,
        confidence: float,
        candidates_analyzed: int,
        strategy_used: str,
        healing_time_ms: float,
        job_id: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> int:
        """Insert healing attempt log."""
        cursor = await self._connection.execute(
            """
            INSERT INTO healing_logs 
            (job_id, original_selector, new_selector, success, confidence,
             candidates_analyzed, strategy_used, healing_time_ms, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                original_selector,
                new_selector,
                success,
                confidence,
                candidates_analyzed,
                strategy_used,
                healing_time_ms,
                error_message
            )
        )
        await self._connection.commit()
        return cursor.lastrowid

    async def get_healing_logs(
        self,
        limit: int = 100,
        success_only: bool = False
    ) -> List[Dict[str, Any]]:
        """Get healing attempt logs."""
        if success_only:
            cursor = await self._connection.execute(
                """
                SELECT * FROM healing_logs 
                WHERE success = TRUE 
                ORDER BY created_at DESC 
                LIMIT ?
                """,
                (limit,)
            )
        else:
            cursor = await self._connection.execute(
                """
                SELECT * FROM healing_logs 
                ORDER BY created_at DESC 
                LIMIT ?
                """,
                (limit,)
            )
        
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def insert_training_data(
        self,
        features: List[float],
        label: int,
        source: str = "healing"
    ) -> None:
        """Insert training data sample."""
        await self._connection.execute(
            """
            INSERT INTO training_data (features, label, source)
            VALUES (?, ?, ?)
            """,
            (json.dumps(features), label, source)
        )
        await self._connection.commit()

    async def save_selector_history(self, url: str, selector: str, element_info: Dict[str, Any]) -> None:
        """Save a successful selector usage with element fingerprint."""
        try:
            await self._connection.execute(
                """
                INSERT INTO selector_history (url, original_selector, new_selector, element_info, status)
                VALUES (?, ?, ?, ?, 'active')
                """,
                (url, selector, selector, json.dumps(element_info))
            )
            await self._connection.commit()
        except Exception as e:
            logger.error(f"Error saving selector history: {e}")

    async def get_last_successful_selector(self, url: str, selector: str) -> Optional[Dict[str, Any]]:
        """Get the last successful scrape for a specific selector.
        Tries exact match first, then fuzzy match by URL with tag prefix."""
        try:
            # Exact match first
            cursor = await self._connection.execute(
                """
                SELECT element_info FROM selector_history 
                WHERE url = ? AND original_selector = ? AND element_info IS NOT NULL
                ORDER BY created_at DESC 
                LIMIT 1
                """,
                (url, selector)
            )
            row = await cursor.fetchone()
            if row and row['element_info']:
                return json.loads(row['element_info'])
            
            # Fuzzy match: find any successful element_info for this URL
            # where the stored selector is a prefix/substring of the broken one
            # e.g., stored "h1" matches broken "h1.broken"
            cursor = await self._connection.execute(
                """
                SELECT original_selector, element_info FROM selector_history 
                WHERE url = ? AND element_info IS NOT NULL
                ORDER BY created_at DESC 
                LIMIT 20
                """,
                (url,)
            )
            rows = await cursor.fetchall()
            
            # Extract just the tag name from the broken selector (e.g., "h1" from "h1.broken")
            import re
            tag_match = re.match(r'^([a-zA-Z][a-zA-Z0-9]*)', selector)
            target_tag = tag_match.group(1).lower() if tag_match else None
            
            for r in rows:
                stored_selector = r['original_selector']
                stored_info = r['element_info']
                if stored_info:
                    info = json.loads(stored_info)
                    # Match by tag name
                    if target_tag and info.get('tag_name', '').lower() == target_tag:
                        logger.info(f"Fuzzy matched history: '{stored_selector}' for broken '{selector}'")
                        return info
            
            return None
        except Exception as e:
            logger.error(f"Error getting selector history: {e}")
            return None

    async def get_training_data(
        self,
        limit: int = 10000
    ) -> List[Dict[str, Any]]:
        """Get training data for model."""
        cursor = await self._connection.execute(
            """
            SELECT features, label FROM training_data 
            ORDER BY created_at DESC 
            LIMIT ?
            """,
            (limit,)
        )
        rows = await cursor.fetchall()
        return [
            {"features": json.loads(row["features"]), "label": row["label"]}
            for row in rows
        ]

    async def get_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        stats = {}
        
        # Selector history count
        cursor = await self._connection.execute(
            "SELECT COUNT(*) as count FROM selector_history"
        )
        row = await cursor.fetchone()
        stats["selector_history_count"] = row["count"]
        
        # Scrape jobs by status
        cursor = await self._connection.execute(
            """
            SELECT status, COUNT(*) as count 
            FROM scrape_jobs 
            GROUP BY status
            """
        )
        rows = await cursor.fetchall()
        stats["jobs_by_status"] = {row["status"]: row["count"] for row in rows}
        
        # Healing success rate
        cursor = await self._connection.execute(
            """
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN success THEN 1 ELSE 0 END) as successes
            FROM healing_logs
            """
        )
        row = await cursor.fetchone()
        total = row["total"] or 0
        successes = row["successes"] or 0
        stats["healing_stats"] = {
            "total": total,
            "successes": successes,
            "success_rate": round(successes / total, 4) if total > 0 else 0
        }
        
        # Training data count
        cursor = await self._connection.execute(
            "SELECT COUNT(*) as count FROM training_data"
        )
        row = await cursor.fetchone()
        stats["training_samples"] = row["count"]
        
        return stats

    # ============ SCRAPE SESSIONS ============

    async def save_scrape_session(self, session_id: str, domain: str, url: str,
                                   session_name: str, container_xpath: str,
                                   products: list, execution_time_ms: float) -> None:
        """Save a product scrape session."""
        await self._connection.execute(
            """INSERT INTO scrape_sessions 
               (id, domain, url, session_name, container_xpath, product_count, products, execution_time_ms)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (session_id, domain, url, session_name, container_xpath,
             len(products), json.dumps(products), execution_time_ms)
        )
        await self._connection.commit()
        logger.info(f"Saved scrape session {session_id} with {len(products)} products")

    async def get_scrape_sessions(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent scrape sessions."""
        cursor = await self._connection.execute(
            """SELECT id, domain, url, session_name, product_count, created_at
               FROM scrape_sessions ORDER BY created_at DESC LIMIT ?""",
            (limit,)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_session_by_id(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get a scrape session with full product data."""
        cursor = await self._connection.execute(
            "SELECT * FROM scrape_sessions WHERE id = ?", (session_id,)
        )
        row = await cursor.fetchone()
        if row:
            data = dict(row)
            data['products'] = json.loads(data.get('products', '[]'))
            return data
        return None


# Singleton database instance
_db_instance: Optional[Database] = None


async def get_database() -> Database:
    """Get or create database instance."""
    global _db_instance
    if _db_instance is None:
        _db_instance = Database()
        await _db_instance.connect()
    return _db_instance
