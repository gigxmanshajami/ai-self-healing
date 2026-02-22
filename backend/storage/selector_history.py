"""
Selector History Module
Manages selector versioning and learning from past changes.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from loguru import logger

from .db import get_database


class SelectorHistory:
    """
    Manages selector history for learning and recovery.
    
    Features:
    - Track selector evolution over time
    - Find working selectors for URLs
    - Provide training data for ML model
    - Rollback to previous selectors
    """

    async def record_selector_change(
        self,
        url: str,
        original_selector: str,
        new_selector: str,
        element_snapshot: Dict[str, Any],
        confidence: float,
        strategy: str
    ) -> int:
        """
        Record a selector change after successful healing.
        
        Args:
            url: Page URL
            original_selector: The failing selector
            new_selector: The healed selector
            element_snapshot: Properties of matched element
            confidence: ML confidence score
            strategy: XPath generation strategy used
            
        Returns:
            Record ID
        """
        db = await get_database()
        record_id = await db.insert_selector_history(
            url=url,
            original_selector=original_selector,
            new_selector=new_selector,
            element_snapshot=element_snapshot,
            confidence=confidence,
            strategy=strategy
        )
        logger.info(f"Recorded selector change: {original_selector} -> {new_selector}")
        return record_id

    async def get_working_selector(
        self,
        url: str,
        original_selector: str
    ) -> Optional[str]:
        """
        Find a known working selector for a URL.
        
        Checks history for previously healed selectors that match.
        
        Args:
            url: Page URL
            original_selector: The selector to look up
            
        Returns:
            Working selector if found, None otherwise
        """
        db = await get_database()
        history = await db.get_selector_history(url=url, limit=10)
        
        for record in history:
            if record["original_selector"] == original_selector:
                if record["new_selector"] and record["status"] == "active":
                    logger.info(f"Found cached selector: {record['new_selector']}")
                    return record["new_selector"]
        
        return None

    async def get_selector_timeline(
        self,
        url: str,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Get selector change timeline for a URL.
        
        Args:
            url: Page URL
            limit: Maximum records to return
            
        Returns:
            List of selector changes with timestamps
        """
        db = await get_database()
        history = await db.get_selector_history(url=url, limit=limit)
        
        return [
            {
                "original": record["original_selector"],
                "new": record["new_selector"],
                "confidence": record["confidence"],
                "strategy": record["strategy"],
                "timestamp": record["created_at"]
            }
            for record in history
        ]

    async def get_all_selectors(
        self,
        active_only: bool = True,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get all stored selectors.
        
        Args:
            active_only: Filter to active selectors only
            limit: Maximum records
            
        Returns:
            List of selector records
        """
        db = await get_database()
        history = await db.get_selector_history(limit=limit)
        
        if active_only:
            history = [h for h in history if h["status"] == "active"]
        
        return history

    async def get_training_samples(
        self,
        since_days: int = 30,
        limit: int = 5000
    ) -> List[Dict[str, Any]]:
        """
        Get training samples from successful healings.
        
        Args:
            since_days: Only include data from last N days
            limit: Maximum samples
            
        Returns:
            Training data with features and labels
        """
        db = await get_database()
        data = await db.get_training_data(limit=limit)
        return data

    async def mark_selector_invalid(
        self,
        record_id: int
    ) -> None:
        """
        Mark a selector as no longer valid.
        
        Call this when a healed selector stops working.
        
        Args:
            record_id: ID of the selector history record
        """
        db = await get_database()
        await db._connection.execute(
            "UPDATE selector_history SET status = 'invalid' WHERE id = ?",
            (record_id,)
        )
        await db._connection.commit()
        logger.info(f"Marked selector {record_id} as invalid")

    async def get_healing_patterns(self) -> Dict[str, Any]:
        """
        Analyze healing patterns for insights.
        
        Returns:
            Statistics about healing patterns
        """
        db = await get_database()
        history = await db.get_selector_history(limit=1000)
        
        patterns = {
            "total_healings": len(history),
            "by_strategy": {},
            "by_confidence_range": {
                "high": 0,    # > 0.8
                "medium": 0,  # 0.6-0.8
                "low": 0      # < 0.6
            },
            "unique_urls": set(),
            "avg_confidence": 0.0
        }
        
        total_confidence = 0.0
        
        for record in history:
            # By strategy
            strategy = record.get("strategy", "unknown")
            patterns["by_strategy"][strategy] = \
                patterns["by_strategy"].get(strategy, 0) + 1
            
            # By confidence
            confidence = record.get("confidence", 0)
            if confidence:
                total_confidence += confidence
                if confidence > 0.8:
                    patterns["by_confidence_range"]["high"] += 1
                elif confidence > 0.6:
                    patterns["by_confidence_range"]["medium"] += 1
                else:
                    patterns["by_confidence_range"]["low"] += 1
            
            # Unique URLs
            patterns["unique_urls"].add(record["url"])
        
        patterns["unique_url_count"] = len(patterns["unique_urls"])
        patterns["unique_urls"] = list(patterns["unique_urls"])[:10]  # Limit for response
        
        if history:
            patterns["avg_confidence"] = round(total_confidence / len(history), 4)
        
    async def get_daily_healing_stats(self, days: int = 7) -> List[Dict[str, Any]]:
        """
        Get healing statistics aggregated by day from healing_logs.
        
        Args:
            days: Number of days to look back
            
        Returns:
            List of daily stats {date, success, failed}
        """
        db = await get_database()
        
        # Calculate start date
        start_date = datetime.now() - timedelta(days=days-1)
        start_str = start_date.strftime("%Y-%m-%d")
        
        query = """
            SELECT 
                DATE(created_at) as date,
                SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as success,
                SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as failed
            FROM healing_logs
            WHERE DATE(created_at) >= ?
            GROUP BY DATE(created_at)
            ORDER BY date ASC
        """
        
        async with db._connection.execute(query, (start_str,)) as cursor:
            rows = await cursor.fetchall()
            
        # Fill in missing dates
        stats = []
        result_map = {row[0]: {"success": row[1], "failed": row[2]} for row in rows}
        
        for i in range(days):
            current_date = start_date + timedelta(days=i)
            date_str = current_date.strftime("%Y-%m-%d")
            day_name = current_date.strftime("%a")
            
            entry = result_map.get(date_str, {"success": 0, "failed": 0})
            stats.append({
                "date": date_str,
                "name": day_name,
                "success": entry["success"],
                "failed": entry["failed"]
            })
            
        return stats

    async def get_aggregated_healing_stats(self) -> Dict[str, Any]:
        """
        Get overall healing statistics from persistent storage.
        
        Returns:
            Dict with total_attempts, success_rate, avg_confidence, etc.
        """
        db = await get_database()
        
        query = """
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successes,
                AVG(confidence) as avg_conf,
                AVG(healing_time_ms) as avg_time
            FROM healing_logs
        """
        
        async with db._connection.execute(query) as cursor:
            row = await cursor.fetchone()
            
        total = row["total"] or 0
        successes = row["successes"] or 0
        avg_conf = row["avg_conf"] or 0.0
        avg_time = row["avg_time"] or 0.0
        
        return {
            "total_attempts": total,
            "success_rate": round(successes / total, 4) if total > 0 else 0.0,
            "avg_confidence": round(avg_conf, 4),
            "avg_healing_time_ms": round(avg_time, 2),
            "successful_healings": successes,
            "failed_healings": total - successes
        }


# Singleton instance
_history_instance: Optional[SelectorHistory] = None


def get_selector_history() -> SelectorHistory:
    """Get selector history instance."""
    global _history_instance
    if _history_instance is None:
        _history_instance = SelectorHistory()
    return _history_instance
