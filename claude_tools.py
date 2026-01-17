"""
Claude Tools - Racing Post data analysis toolkit for Claude Code.

Provides direct database access and pre-built queries for analyzing
Racing Post scraper data, coverage gaps, and data quality.

Usage:
    from claude_tools import ClaudeTools
    ct = ClaudeTools()

    ct.health_check()              # Is everything working?
    ct.get_data_summary()          # Overview of all tables
    ct.get_date_coverage()         # Which dates have data?
    ct.find_missing_runs()         # Races without run data
    ct.get_stats_coverage()        # Racecard/stats coverage
    ct.get_race_details(123)       # Full race with runners
    ct.get_horse_history(456)      # Horse's race history
    ct.run_sql("SELECT ...")       # Custom SQL query
"""

import os
from datetime import datetime, timedelta
from typing import Optional

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

# Database config - NAS production database
DB_HOST = os.getenv("DATABASE_HOST", "localhost")
DB_PORT = os.getenv("DATABASE_PORT", "5433")
DB_NAME = os.getenv("DATABASE_NAME", "maindb")
DB_USER = os.getenv("DATABASE_USER", "postgres")
DB_PASSWORD = os.getenv("DATABASE_PASSWORD", "REMOVED")


class ClaudeTools:
    """Racing Post data analysis toolkit for Claude Code."""

    def __init__(self):
        self._conn = None

    # =========================================================================
    # Database Connection
    # =========================================================================

    def _get_conn(self):
        """Get or create database connection."""
        if self._conn is None or self._conn.closed:
            self._conn = psycopg2.connect(
                host=DB_HOST,
                port=DB_PORT,
                dbname=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD,
            )
        return self._conn

    def close(self):
        """Close database connection."""
        if self._conn and not self._conn.closed:
            self._conn.close()

    # =========================================================================
    # Raw SQL Methods
    # =========================================================================

    def run_sql(self, query: str, params: tuple = None) -> list[dict]:
        """
        Execute SQL query and return results as list of dicts.

        Args:
            query: SQL query string (use %s for params)
            params: Optional tuple of query parameters

        Returns:
            List of dicts, one per row

        Example:
            ct.run_sql("SELECT * FROM rp_race WHERE race_id = %s", (123,))
        """
        conn = self._get_conn()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params)
            if cur.description:
                return [dict(row) for row in cur.fetchall()]
            conn.commit()
            return []

    def execute_sql(self, query: str, params: tuple = None, dry_run: bool = False) -> dict:
        """
        Execute a write SQL statement (INSERT/UPDATE/DELETE).

        Args:
            query: SQL statement (INSERT, UPDATE, DELETE)
            params: Optional tuple of query parameters
            dry_run: If True, rollback instead of commit (preview mode)

        Returns:
            Dict with rows_affected and status

        Example:
            ct.execute_sql("DELETE FROM rp_trainer WHERE trainer_id = %s", (123,))
            ct.execute_sql("UPDATE rp_horse SET name = %s WHERE horse_id = %s", ('New Name', 456))
        """
        conn = self._get_conn()
        with conn.cursor() as cur:
            cur.execute(query, params)
            rows_affected = cur.rowcount

            if dry_run:
                conn.rollback()
                return {
                    "status": "dry_run",
                    "rows_affected": rows_affected,
                    "message": f"Would affect {rows_affected} rows (rolled back)",
                }
            else:
                conn.commit()
                return {
                    "status": "success",
                    "rows_affected": rows_affected,
                    "message": f"Affected {rows_affected} rows",
                }

    def get_tables(self) -> list[str]:
        """Get list of all Racing Post table names."""
        query = """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name LIKE 'rp_%'
            ORDER BY table_name
        """
        return [r["table_name"] for r in self.run_sql(query)]

    def get_table_info(self, table: str) -> dict:
        """
        Get detailed info about a table.

        Returns:
            Dict with columns, row_count, sample_data
        """
        # Get columns
        col_query = """
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = %s
            ORDER BY ordinal_position
        """
        columns = self.run_sql(col_query, (table,))

        # Get row count
        count_result = self.run_sql(f"SELECT COUNT(*) as cnt FROM {table}")
        row_count = count_result[0]["cnt"] if count_result else 0

        # Get sample rows
        sample = self.run_sql(f"SELECT * FROM {table} LIMIT 3")

        return {
            "table": table,
            "columns": columns,
            "row_count": row_count,
            "sample": sample,
        }

    # =========================================================================
    # Date Helpers
    # =========================================================================

    @staticmethod
    def today() -> str:
        """Get today's date as YYYY-MM-DD string."""
        return datetime.now().strftime("%Y-%m-%d")

    @staticmethod
    def yesterday() -> str:
        """Get yesterday's date as YYYY-MM-DD string."""
        return (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    # =========================================================================
    # Data Summary
    # =========================================================================

    def get_data_summary(self) -> dict:
        """
        Get overview of all Racing Post tables with row counts.

        Returns:
            Dict with table names and row counts
        """
        query = """
            SELECT 'rp_course' as tbl, COUNT(*) as cnt FROM rp_course
            UNION ALL SELECT 'rp_horse', COUNT(*) FROM rp_horse
            UNION ALL SELECT 'rp_jockey', COUNT(*) FROM rp_jockey
            UNION ALL SELECT 'rp_trainer', COUNT(*) FROM rp_trainer
            UNION ALL SELECT 'rp_owner', COUNT(*) FROM rp_owner
            UNION ALL SELECT 'rp_breeder', COUNT(*) FROM rp_breeder
            UNION ALL SELECT 'rp_race', COUNT(*) FROM rp_race
            UNION ALL SELECT 'rp_run', COUNT(*) FROM rp_run
            UNION ALL SELECT 'rp_racecard_entry', COUNT(*) FROM rp_racecard_entry
            UNION ALL SELECT 'rp_horse_race_stats', COUNT(*) FROM rp_horse_race_stats
            UNION ALL SELECT 'rp_jockey_stats_daily', COUNT(*) FROM rp_jockey_stats_daily
            UNION ALL SELECT 'rp_trainer_stats_daily', COUNT(*) FROM rp_trainer_stats_daily
            UNION ALL SELECT 'rp_horse_trainer_history', COUNT(*) FROM rp_horse_trainer_history
            UNION ALL SELECT 'rp_horse_owner_history', COUNT(*) FROM rp_horse_owner_history
            UNION ALL SELECT 'rp_horse_medical', COUNT(*) FROM rp_horse_medical
            UNION ALL SELECT 'rp_betfair_price', COUNT(*) FROM rp_betfair_price
            UNION ALL SELECT 'rp_betfair_mapping', COUNT(*) FROM rp_betfair_mapping
            ORDER BY 1
        """
        rows = self.run_sql(query)
        return {r["tbl"]: r["cnt"] for r in rows}

    # =========================================================================
    # Data Quality
    # =========================================================================

    def check_data_quality(self) -> dict:
        """
        Run comprehensive data quality checks.

        Returns:
            Dict with quality metrics and issues found
        """
        results = {
            "checked_at": datetime.now().isoformat(),
            "issues": [],
        }

        # Check for orphaned runs (runs without race)
        orphan_query = """
            SELECT COUNT(*) as cnt
            FROM rp_run r
            LEFT JOIN rp_race rc ON r.race_id = rc.race_id
            WHERE rc.race_id IS NULL
        """
        orphans = self.run_sql(orphan_query)[0]["cnt"]
        results["orphaned_runs"] = orphans
        if orphans > 0:
            results["issues"].append(f"{orphans} runs without matching race")

        # Check for null values in key fields
        null_query = """
            SELECT
                SUM(CASE WHEN position IS NULL THEN 1 ELSE 0 END) as null_pos,
                SUM(CASE WHEN sp IS NULL THEN 1 ELSE 0 END) as null_sp,
                SUM(CASE WHEN jockey_id IS NULL THEN 1 ELSE 0 END) as null_jockey,
                SUM(CASE WHEN trainer_id IS NULL THEN 1 ELSE 0 END) as null_trainer,
                COUNT(*) as total
            FROM rp_run
        """
        nulls = self.run_sql(null_query)[0]
        results["null_checks"] = {
            "position": nulls["null_pos"],
            "sp": nulls["null_sp"],
            "jockey": nulls["null_jockey"],
            "trainer": nulls["null_trainer"],
            "total_runs": nulls["total"],
        }

        # Check runner count mismatches
        mismatch_query = """
            SELECT COUNT(*) as cnt
            FROM rp_race r
            LEFT JOIN (
                SELECT race_id, COUNT(*) as actual_runs
                FROM rp_run
                GROUP BY race_id
            ) ru ON r.race_id = ru.race_id
            WHERE r.runners != COALESCE(ru.actual_runs, 0)
              AND r.date < CURRENT_DATE
        """
        mismatches = self.run_sql(mismatch_query)[0]["cnt"]
        results["runner_mismatches"] = mismatches
        if mismatches > 0:
            results["issues"].append(f"{mismatches} races with runner count mismatch")

        results["status"] = "OK" if not results["issues"] else "ISSUES_FOUND"
        return results

    def find_missing_runs(self, limit: int = 20) -> list[dict]:
        """
        Find races that have no run data (past races only).

        Args:
            limit: Maximum number of results

        Returns:
            List of races missing run data
        """
        query = """
            SELECT
                r.race_id,
                r.date,
                c.name as course,
                r.race_name,
                r.runners as expected_runners
            FROM rp_race r
            JOIN rp_course c ON r.course_id = c.course_id
            LEFT JOIN rp_run ru ON r.race_id = ru.race_id
            WHERE r.date < CURRENT_DATE
            GROUP BY r.race_id, r.date, c.name, r.race_name, r.runners
            HAVING COUNT(ru.id) = 0
            ORDER BY r.date DESC
            LIMIT %s
        """
        return self.run_sql(query, (limit,))

    def find_incomplete_races(self, limit: int = 20) -> list[dict]:
        """
        Find races where runner count doesn't match actual runs.

        Args:
            limit: Maximum number of results

        Returns:
            List of races with mismatched runner counts
        """
        query = """
            SELECT
                r.race_id,
                r.date,
                c.name as course,
                r.race_name,
                r.runners as expected,
                COUNT(ru.id) as actual
            FROM rp_race r
            JOIN rp_course c ON r.course_id = c.course_id
            LEFT JOIN rp_run ru ON r.race_id = ru.race_id
            WHERE r.date < CURRENT_DATE
            GROUP BY r.race_id, r.date, c.name, r.race_name, r.runners
            HAVING r.runners != COUNT(ru.id) AND COUNT(ru.id) > 0
            ORDER BY r.date DESC
            LIMIT %s
        """
        return self.run_sql(query, (limit,))

    # =========================================================================
    # Date Coverage
    # =========================================================================

    def get_date_coverage(self, days: int = 14) -> list[dict]:
        """
        Get data coverage by date for recent days.

        Args:
            days: Number of days to look back

        Returns:
            List of dicts with date, race count, run coverage, stats coverage
        """
        query = """
            SELECT
                r.date,
                COUNT(DISTINCT r.race_id) as races,
                COUNT(DISTINCT CASE WHEN ru.id IS NOT NULL THEN r.race_id END) as with_runs,
                COUNT(DISTINCT CASE WHEN ru.id IS NULL THEN r.race_id END) as without_runs,
                COUNT(DISTINCT rc.race_id) as with_racecard,
                COUNT(DISTINCT hrs.race_id) as with_stats
            FROM rp_race r
            LEFT JOIN rp_run ru ON r.race_id = ru.race_id
            LEFT JOIN rp_racecard_entry rc ON r.race_id = rc.race_id
            LEFT JOIN rp_horse_race_stats hrs ON r.race_id = hrs.race_id
            WHERE r.date >= CURRENT_DATE - INTERVAL '%s days'
            GROUP BY r.date
            ORDER BY r.date DESC
        """
        return self.run_sql(query, (days,))

    def get_date_range(self) -> dict:
        """
        Get the date range of race data in the database.

        Returns:
            Dict with earliest, latest, total_days, total_races
        """
        query = """
            SELECT
                MIN(date) as earliest,
                MAX(date) as latest,
                COUNT(DISTINCT date) as total_days,
                COUNT(*) as total_races
            FROM rp_race
        """
        result = self.run_sql(query)[0]
        return {
            "earliest": str(result["earliest"]) if result["earliest"] else None,
            "latest": str(result["latest"]) if result["latest"] else None,
            "total_days": result["total_days"],
            "total_races": result["total_races"],
        }

    # =========================================================================
    # Stats Coverage
    # =========================================================================

    def get_stats_coverage(self, days: int = 7) -> dict:
        """
        Get coverage of time-sensitive stats data.

        Args:
            days: Number of days to check

        Returns:
            Dict with coverage stats for racecards, jockey/trainer stats
        """
        # Racecard coverage
        racecard_query = """
            SELECT
                r.date,
                COUNT(DISTINCT r.race_id) as total_races,
                COUNT(DISTINCT rc.race_id) as with_racecard,
                COUNT(DISTINCT hrs.race_id) as with_horse_stats
            FROM rp_race r
            LEFT JOIN rp_racecard_entry rc ON r.race_id = rc.race_id
            LEFT JOIN rp_horse_race_stats hrs ON r.race_id = hrs.race_id
            WHERE r.date >= CURRENT_DATE - INTERVAL '%s days'
            GROUP BY r.date
            ORDER BY r.date DESC
        """
        racecard_data = self.run_sql(racecard_query, (days,))

        # Jockey/trainer daily stats
        jt_query = """
            SELECT
                date,
                (SELECT COUNT(*) FROM rp_jockey_stats_daily WHERE date = d.date) as jockey_stats,
                (SELECT COUNT(*) FROM rp_trainer_stats_daily WHERE date = d.date) as trainer_stats
            FROM (
                SELECT DISTINCT date FROM rp_race
                WHERE date >= CURRENT_DATE - INTERVAL '%s days'
            ) d
            ORDER BY date DESC
        """
        jt_data = self.run_sql(jt_query, (days,))

        return {
            "days_checked": days,
            "racecard_coverage": [{
                "date": str(r["date"]),
                "races": r["total_races"],
                "with_racecard": r["with_racecard"],
                "with_horse_stats": r["with_horse_stats"],
                "racecard_pct": round(r["with_racecard"] / r["total_races"] * 100, 1) if r["total_races"] > 0 else 0,
            } for r in racecard_data],
            "daily_stats": [{
                "date": str(r["date"]),
                "jockey_stats": r["jockey_stats"],
                "trainer_stats": r["trainer_stats"],
            } for r in jt_data],
        }

    # =========================================================================
    # BSP Coverage
    # =========================================================================

    def get_bsp_coverage(self, days: int = 7) -> dict:
        """
        Get Betfair BSP data coverage.

        Args:
            days: Number of days to check

        Returns:
            Dict with BSP coverage stats
        """
        query = """
            SELECT
                r.date,
                COUNT(DISTINCT ru.id) as total_runs,
                COUNT(DISTINCT bp.run_id) as with_bsp,
                ROUND(100.0 * COUNT(DISTINCT bp.run_id) / NULLIF(COUNT(DISTINCT ru.id), 0), 1) as bsp_pct
            FROM rp_race r
            JOIN rp_run ru ON r.race_id = ru.race_id
            LEFT JOIN rp_betfair_price bp ON ru.id = bp.run_id
            WHERE r.date >= CURRENT_DATE - INTERVAL '%s days'
              AND r.date < CURRENT_DATE
            GROUP BY r.date
            ORDER BY r.date DESC
        """
        data = self.run_sql(query, (days,))

        total_runs = sum(r["total_runs"] for r in data)
        total_bsp = sum(r["with_bsp"] for r in data)

        return {
            "days_checked": days,
            "overall": {
                "total_runs": total_runs,
                "with_bsp": total_bsp,
                "coverage_pct": round(100.0 * total_bsp / total_runs, 1) if total_runs > 0 else 0,
            },
            "by_date": [{
                "date": str(r["date"]),
                "runs": r["total_runs"],
                "with_bsp": r["with_bsp"],
                "pct": float(r["bsp_pct"]) if r["bsp_pct"] else 0,
            } for r in data],
        }

    # =========================================================================
    # Race Lookups
    # =========================================================================

    def get_races_by_date(self, date: str) -> list[dict]:
        """
        Get all races for a specific date.

        Args:
            date: YYYY-MM-DD string

        Returns:
            List of race dicts
        """
        query = """
            SELECT
                r.race_id,
                r.off_time,
                c.name as course,
                r.race_name,
                r.race_type,
                r.distance,
                r.going,
                r.runners,
                (SELECT COUNT(*) FROM rp_run WHERE race_id = r.race_id) as actual_runs,
                (SELECT COUNT(*) FROM rp_racecard_entry WHERE race_id = r.race_id) as racecard_entries
            FROM rp_race r
            JOIN rp_course c ON r.course_id = c.course_id
            WHERE r.date = %s
            ORDER BY r.off_time
        """
        return self.run_sql(query, (date,))

    def get_race_details(self, race_id: int) -> dict:
        """
        Get full race details including all runners.

        Args:
            race_id: Racing Post race ID

        Returns:
            Dict with race info and runners
        """
        # Get race info
        race_query = """
            SELECT
                r.*,
                c.name as course_name
            FROM rp_race r
            JOIN rp_course c ON r.course_id = c.course_id
            WHERE r.race_id = %s
        """
        races = self.run_sql(race_query, (race_id,))
        if not races:
            return {"error": f"Race {race_id} not found"}

        race = races[0]

        # Get runners
        runners_query = """
            SELECT
                ru.*,
                h.name as horse_name,
                j.name as jockey_name,
                t.name as trainer_name,
                bp.bsp
            FROM rp_run ru
            JOIN rp_horse h ON ru.horse_id = h.horse_id
            LEFT JOIN rp_jockey j ON ru.jockey_id = j.jockey_id
            LEFT JOIN rp_trainer t ON ru.trainer_id = t.trainer_id
            LEFT JOIN rp_betfair_price bp ON ru.id = bp.run_id
            WHERE ru.race_id = %s
            ORDER BY ru.position_numeric NULLS LAST, ru.cloth_number
        """
        runners = self.run_sql(runners_query, (race_id,))

        return {
            "race": {
                "race_id": race["race_id"],
                "date": str(race["date"]),
                "off_time": race["off_time"],
                "course": race["course_name"],
                "race_name": race["race_name"],
                "race_type": race["race_type"],
                "distance": race["distance"],
                "going": race["going"],
                "race_class": race["race_class"],
                "prize": float(race["prize"]) if race["prize"] else None,
            },
            "runners": [{
                "position": r["position"],
                "cloth": r["cloth_number"],
                "horse": r["horse_name"],
                "horse_id": r["horse_id"],
                "jockey": r["jockey_name"],
                "trainer": r["trainer_name"],
                "sp": r["sp"],
                "sp_decimal": float(r["sp_decimal"]) if r["sp_decimal"] else None,
                "bsp": float(r["bsp"]) if r["bsp"] else None,
                "age": r["age"],
                "weight": r["weight"],
                "or": r["official_rating"],
                "rpr": r["rpr"],
            } for r in runners],
        }

    # =========================================================================
    # Horse Lookups
    # =========================================================================

    def get_horse_history(self, horse_id: int) -> dict:
        """
        Get horse's race history.

        Args:
            horse_id: Racing Post horse ID

        Returns:
            Dict with horse info and race history
        """
        # Get horse info
        horse_query = "SELECT * FROM rp_horse WHERE horse_id = %s"
        horses = self.run_sql(horse_query, (horse_id,))
        if not horses:
            return {"error": f"Horse {horse_id} not found"}

        horse = horses[0]

        # Get race history
        history_query = """
            SELECT
                r.date,
                r.off_time,
                c.name as course,
                r.race_name,
                r.distance,
                r.going,
                ru.position,
                ru.sp,
                ru.sp_decimal,
                j.name as jockey,
                t.name as trainer,
                ru.official_rating,
                ru.rpr,
                bp.bsp
            FROM rp_run ru
            JOIN rp_race r ON ru.race_id = r.race_id
            JOIN rp_course c ON r.course_id = c.course_id
            LEFT JOIN rp_jockey j ON ru.jockey_id = j.jockey_id
            LEFT JOIN rp_trainer t ON ru.trainer_id = t.trainer_id
            LEFT JOIN rp_betfair_price bp ON ru.id = bp.run_id
            WHERE ru.horse_id = %s
            ORDER BY r.date DESC, r.off_time DESC
        """
        history = self.run_sql(history_query, (horse_id,))

        # Get medical history
        medical_query = """
            SELECT * FROM rp_horse_medical
            WHERE horse_id = %s
            ORDER BY procedure_date DESC
        """
        medical = self.run_sql(medical_query, (horse_id,))

        # Get trainer history
        trainer_query = """
            SELECT th.*, t.name as to_trainer_name
            FROM rp_horse_trainer_history th
            LEFT JOIN rp_trainer t ON th.to_trainer_id = t.trainer_id
            WHERE th.horse_id = %s
            ORDER BY th.change_date DESC
        """
        trainers = self.run_sql(trainer_query, (horse_id,))

        return {
            "horse": {
                "horse_id": horse["horse_id"],
                "name": horse["name"],
                "region": horse.get("region"),
                "dob": str(horse["dob"]) if horse.get("dob") else None,
                "colour": horse.get("colour"),
                "sex": horse.get("sex"),
            },
            "runs": len(history),
            "history": [{
                "date": str(r["date"]),
                "course": r["course"],
                "race": r["race_name"],
                "distance": r["distance"],
                "going": r["going"],
                "position": r["position"],
                "sp": r["sp"],
                "bsp": float(r["bsp"]) if r["bsp"] else None,
                "jockey": r["jockey"],
                "trainer": r["trainer"],
                "or": r["official_rating"],
                "rpr": r["rpr"],
            } for r in history],
            "medical": medical,
            "trainers": trainers,
        }

    def search_horse(self, name: str, limit: int = 10) -> list[dict]:
        """
        Search for horses by name.

        Args:
            name: Partial horse name to search
            limit: Maximum results

        Returns:
            List of matching horses
        """
        query = """
            SELECT
                h.horse_id,
                h.name,
                h.region,
                h.dob,
                (SELECT COUNT(*) FROM rp_run WHERE horse_id = h.horse_id) as runs
            FROM rp_horse h
            WHERE LOWER(h.name) LIKE LOWER(%s)
            ORDER BY runs DESC
            LIMIT %s
        """
        return self.run_sql(query, (f"%{name}%", limit))

    # =========================================================================
    # Course Analysis
    # =========================================================================

    def get_course_summary(self) -> list[dict]:
        """
        Get summary of all courses with race counts.

        Returns:
            List of courses with race/run stats
        """
        query = """
            SELECT
                c.course_id,
                c.name,
                COUNT(DISTINCT r.race_id) as races,
                COUNT(DISTINCT ru.id) as runs,
                MIN(r.date) as first_race,
                MAX(r.date) as last_race
            FROM rp_course c
            LEFT JOIN rp_race r ON c.course_id = r.course_id
            LEFT JOIN rp_run ru ON r.race_id = ru.race_id
            GROUP BY c.course_id, c.name
            ORDER BY races DESC
        """
        return self.run_sql(query)

    # =========================================================================
    # Health Check
    # =========================================================================

    def health_check(self) -> dict:
        """
        Check system health - database connection, recent data.

        Returns:
            Dict with status of each component
        """
        result = {
            "timestamp": datetime.now().isoformat(),
            "db": {"status": "unknown"},
            "data": {"status": "unknown"},
        }

        # Check DB connection
        try:
            self.run_sql("SELECT 1")
            result["db"] = {"status": "ok", "host": DB_HOST, "port": DB_PORT}
        except Exception as e:
            result["db"] = {"status": "error", "error": str(e)}
            result["overall"] = "unhealthy"
            return result

        # Check recent data
        try:
            date_range = self.get_date_range()
            latest = date_range.get("latest")
            today = self.today()

            if latest:
                days_behind = (datetime.strptime(today, "%Y-%m-%d") -
                               datetime.strptime(latest, "%Y-%m-%d")).days
                result["data"] = {
                    "status": "ok" if days_behind <= 1 else "stale",
                    "latest_date": latest,
                    "days_behind": days_behind,
                    "total_races": date_range["total_races"],
                }
            else:
                result["data"] = {"status": "empty", "message": "No race data"}
        except Exception as e:
            result["data"] = {"status": "error", "error": str(e)}

        # Overall status
        if result["db"]["status"] == "ok" and result["data"]["status"] == "ok":
            result["overall"] = "healthy"
        elif result["db"]["status"] == "error" or result["data"]["status"] == "error":
            result["overall"] = "unhealthy"
        else:
            result["overall"] = "degraded"

        return result

    # =========================================================================
    # Duplicate Detection & Cleanup
    # =========================================================================

    def find_duplicate_trainers(self) -> list[dict]:
        """
        Find trainers with duplicate names.

        Returns:
            List of duplicate trainer groups with usage stats
        """
        query = """
            WITH trainer_usage AS (
                SELECT
                    t.trainer_id,
                    t.name,
                    (SELECT COUNT(*) FROM rp_run WHERE trainer_id = t.trainer_id) as run_count,
                    (SELECT COUNT(*) FROM rp_horse_trainer_history WHERE to_trainer_id = t.trainer_id) as history_count
                FROM rp_trainer t
            )
            SELECT *
            FROM trainer_usage
            WHERE name IN (
                SELECT name FROM rp_trainer
                GROUP BY name HAVING COUNT(*) > 1
            )
            ORDER BY name, run_count DESC, trainer_id
        """
        return self.run_sql(query)

    def find_duplicate_jockeys(self) -> list[dict]:
        """
        Find jockeys with duplicate names.

        Returns:
            List of duplicate jockey groups with usage stats
        """
        query = """
            WITH jockey_usage AS (
                SELECT
                    j.jockey_id,
                    j.name,
                    (SELECT COUNT(*) FROM rp_run WHERE jockey_id = j.jockey_id) as run_count,
                    (SELECT COUNT(*) FROM rp_jockey_stats_daily WHERE jockey_id = j.jockey_id) as stats_count
                FROM rp_jockey j
            )
            SELECT *
            FROM jockey_usage
            WHERE name IN (
                SELECT name FROM rp_jockey
                GROUP BY name HAVING COUNT(*) > 1
            )
            ORDER BY name, run_count DESC, jockey_id
        """
        return self.run_sql(query)

    def find_duplicate_owners(self) -> list[dict]:
        """
        Find owners with duplicate names.

        Returns:
            List of duplicate owner groups with usage stats
        """
        query = """
            WITH owner_usage AS (
                SELECT
                    o.owner_id,
                    o.name,
                    (SELECT COUNT(*) FROM rp_run WHERE owner_id = o.owner_id) as run_count,
                    (SELECT COUNT(*) FROM rp_horse_owner_history WHERE to_owner_id = o.owner_id) as history_count
                FROM rp_owner o
            )
            SELECT *
            FROM owner_usage
            WHERE name IN (
                SELECT name FROM rp_owner
                GROUP BY name HAVING COUNT(*) > 1
            )
            ORDER BY name, run_count DESC, owner_id
        """
        return self.run_sql(query)

    def cleanup_duplicate_trainers(self, dry_run: bool = True) -> dict:
        """
        Clean up duplicate trainers by merging to the most-used ID.

        For each duplicate name:
        1. Keep the trainer_id with the most runs
        2. Update any references to point to the kept ID
        3. Delete the unused duplicate IDs

        Args:
            dry_run: If True, show what would happen without making changes

        Returns:
            Dict with cleanup results
        """
        results = {
            "dry_run": dry_run,
            "duplicates_found": 0,
            "records_updated": 0,
            "records_deleted": 0,
            "details": [],
        }

        # Find duplicates grouped by name
        dupes = self.find_duplicate_trainers()
        if not dupes:
            results["message"] = "No duplicate trainers found"
            return results

        # Group by name
        groups = {}
        for d in dupes:
            name = d["name"]
            if name not in groups:
                groups[name] = []
            groups[name].append(d)

        results["duplicates_found"] = len(groups)

        for name, trainers in groups.items():
            # First one has most runs (sorted in query)
            keep_id = trainers[0]["trainer_id"]
            delete_ids = [t["trainer_id"] for t in trainers[1:]]

            detail = {
                "name": name,
                "keep_id": keep_id,
                "delete_ids": delete_ids,
                "updates": [],
                "deletes": 0,
            }

            for del_id in delete_ids:
                # Update rp_run references
                update_result = self.execute_sql(
                    "UPDATE rp_run SET trainer_id = %s WHERE trainer_id = %s",
                    (keep_id, del_id),
                    dry_run=dry_run
                )
                if update_result["rows_affected"] > 0:
                    detail["updates"].append(f"rp_run: {update_result['rows_affected']}")
                    results["records_updated"] += update_result["rows_affected"]

                # Update rp_racecard_entry references
                update_result = self.execute_sql(
                    "UPDATE rp_racecard_entry SET trainer_id = %s WHERE trainer_id = %s",
                    (keep_id, del_id),
                    dry_run=dry_run
                )
                if update_result["rows_affected"] > 0:
                    detail["updates"].append(f"rp_racecard_entry: {update_result['rows_affected']}")
                    results["records_updated"] += update_result["rows_affected"]

                # Update rp_horse_trainer_history references
                update_result = self.execute_sql(
                    "UPDATE rp_horse_trainer_history SET to_trainer_id = %s WHERE to_trainer_id = %s",
                    (keep_id, del_id),
                    dry_run=dry_run
                )
                if update_result["rows_affected"] > 0:
                    detail["updates"].append(f"rp_horse_trainer_history.to: {update_result['rows_affected']}")
                    results["records_updated"] += update_result["rows_affected"]

                update_result = self.execute_sql(
                    "UPDATE rp_horse_trainer_history SET from_trainer_id = %s WHERE from_trainer_id = %s",
                    (keep_id, del_id),
                    dry_run=dry_run
                )
                if update_result["rows_affected"] > 0:
                    detail["updates"].append(f"rp_horse_trainer_history.from: {update_result['rows_affected']}")
                    results["records_updated"] += update_result["rows_affected"]

                # Update rp_trainer_stats_daily references
                update_result = self.execute_sql(
                    "UPDATE rp_trainer_stats_daily SET trainer_id = %s WHERE trainer_id = %s",
                    (keep_id, del_id),
                    dry_run=dry_run
                )
                if update_result["rows_affected"] > 0:
                    detail["updates"].append(f"rp_trainer_stats_daily: {update_result['rows_affected']}")
                    results["records_updated"] += update_result["rows_affected"]

                # Delete the duplicate trainer
                delete_result = self.execute_sql(
                    "DELETE FROM rp_trainer WHERE trainer_id = %s",
                    (del_id,),
                    dry_run=dry_run
                )
                detail["deletes"] += delete_result["rows_affected"]
                results["records_deleted"] += delete_result["rows_affected"]

            results["details"].append(detail)

        results["message"] = f"{'Would clean' if dry_run else 'Cleaned'} {results['duplicates_found']} duplicate trainer names"
        return results

    def cleanup_duplicate_owners(self, dry_run: bool = True) -> dict:
        """
        Clean up duplicate owners by merging to the most-used ID.

        Args:
            dry_run: If True, show what would happen without making changes

        Returns:
            Dict with cleanup results
        """
        results = {
            "dry_run": dry_run,
            "duplicates_found": 0,
            "records_updated": 0,
            "records_deleted": 0,
            "details": [],
        }

        dupes = self.find_duplicate_owners()
        if not dupes:
            results["message"] = "No duplicate owners found"
            return results

        # Group by name
        groups = {}
        for d in dupes:
            name = d["name"]
            if name not in groups:
                groups[name] = []
            groups[name].append(d)

        results["duplicates_found"] = len(groups)

        for name, owners in groups.items():
            keep_id = owners[0]["owner_id"]
            delete_ids = [o["owner_id"] for o in owners[1:]]

            detail = {
                "name": name,
                "keep_id": keep_id,
                "delete_ids": delete_ids,
                "updates": [],
                "deletes": 0,
            }

            for del_id in delete_ids:
                # Update rp_run references
                update_result = self.execute_sql(
                    "UPDATE rp_run SET owner_id = %s WHERE owner_id = %s",
                    (keep_id, del_id),
                    dry_run=dry_run
                )
                if update_result["rows_affected"] > 0:
                    detail["updates"].append(f"rp_run: {update_result['rows_affected']}")
                    results["records_updated"] += update_result["rows_affected"]

                # Update rp_racecard_entry references
                update_result = self.execute_sql(
                    "UPDATE rp_racecard_entry SET owner_id = %s WHERE owner_id = %s",
                    (keep_id, del_id),
                    dry_run=dry_run
                )
                if update_result["rows_affected"] > 0:
                    detail["updates"].append(f"rp_racecard_entry: {update_result['rows_affected']}")
                    results["records_updated"] += update_result["rows_affected"]

                # Update rp_horse_owner_history references (to_owner_id)
                update_result = self.execute_sql(
                    "UPDATE rp_horse_owner_history SET to_owner_id = %s WHERE to_owner_id = %s",
                    (keep_id, del_id),
                    dry_run=dry_run
                )
                if update_result["rows_affected"] > 0:
                    detail["updates"].append(f"rp_horse_owner_history.to: {update_result['rows_affected']}")
                    results["records_updated"] += update_result["rows_affected"]

                # Update rp_horse_owner_history references (from_owner_id)
                update_result = self.execute_sql(
                    "UPDATE rp_horse_owner_history SET from_owner_id = %s WHERE from_owner_id = %s",
                    (keep_id, del_id),
                    dry_run=dry_run
                )
                if update_result["rows_affected"] > 0:
                    detail["updates"].append(f"rp_horse_owner_history.from: {update_result['rows_affected']}")
                    results["records_updated"] += update_result["rows_affected"]

                # Delete the duplicate owner
                delete_result = self.execute_sql(
                    "DELETE FROM rp_owner WHERE owner_id = %s",
                    (del_id,),
                    dry_run=dry_run
                )
                detail["deletes"] += delete_result["rows_affected"]
                results["records_deleted"] += delete_result["rows_affected"]

            results["details"].append(detail)

        results["message"] = f"{'Would clean' if dry_run else 'Cleaned'} {results['duplicates_found']} duplicate owner names"
        return results

    def find_all_duplicates(self) -> dict:
        """
        Find all duplicate records across key tables.

        Returns:
            Dict with duplicate counts and details for each table
        """
        return {
            "trainers": self.find_duplicate_trainers(),
            "jockeys": self.find_duplicate_jockeys(),
            "owners": self.find_duplicate_owners(),
            "summary": {
                "duplicate_trainer_names": len(set(t["name"] for t in self.find_duplicate_trainers())),
                "duplicate_jockey_names": len(set(j["name"] for j in self.find_duplicate_jockeys())),
                "duplicate_owner_names": len(set(o["name"] for o in self.find_duplicate_owners())),
            }
        }

    # =========================================================================
    # Report Methods (for prompts)
    # =========================================================================

    def get_daily_report(self, date: str = None) -> dict:
        """
        Get comprehensive daily report for racecard monitoring.

        Args:
            date: YYYY-MM-DD string (default: today)

        Returns:
            Dict containing all key metrics for daily trading report:
            - health: System health status
            - races_today: All races for the date
            - stats_coverage: Racecard/stats coverage
            - data_quality: Quality check results
            - date_coverage: Recent date coverage

        Use this as the primary method for live trading day monitoring.
        """
        date = date or self.today()

        # Get today's races
        races = self.get_races_by_date(date)
        races_with_racecard = sum(1 for r in races if r["racecard_entries"] > 0)
        races_with_runs = sum(1 for r in races if r["actual_runs"] > 0)

        return {
            "date": date,
            "generated_at": datetime.now().isoformat(),
            "health": self.health_check(),
            "races_today": {
                "total": len(races),
                "with_racecard": races_with_racecard,
                "with_runs": races_with_runs,
                "racecard_pct": round(100 * races_with_racecard / len(races), 1) if races else 0,
                "races": races[:20],  # First 20 races
            },
            "stats_coverage": self.get_stats_coverage(days=7),
            "data_quality": self.check_data_quality(),
            "date_coverage": self.get_date_coverage(days=7),
        }

    def get_report_summary(self, date: str = None) -> dict:
        """
        Get comprehensive summary for end-of-day validation report.

        Args:
            date: YYYY-MM-DD string (default: yesterday)

        Returns:
            Dict containing all key metrics for EOD report:
            - health: System health status
            - data_summary: Table row counts
            - date_range: Overall data range
            - yesterday: Yesterday's race coverage
            - bsp_coverage: BSP data coverage
            - data_quality: Quality check results
            - missing_runs: Races without run data
            - incomplete_races: Runner count mismatches

        Use this as the primary method for end-of-day validation.
        """
        date = date or self.yesterday()

        # Get yesterday's races
        races = self.get_races_by_date(date)
        races_with_runs = sum(1 for r in races if r["actual_runs"] > 0)
        incomplete = [r for r in races if r["actual_runs"] > 0 and r["runners"] != r["actual_runs"]]

        return {
            "date": date,
            "generated_at": datetime.now().isoformat(),
            "health": self.health_check(),
            "data_summary": self.get_data_summary(),
            "date_range": self.get_date_range(),
            "yesterday": {
                "total_races": len(races),
                "with_runs": races_with_runs,
                "coverage_pct": round(100 * races_with_runs / len(races), 1) if races else 0,
                "incomplete_count": len(incomplete),
                "races": races,
            },
            "bsp_coverage": self.get_bsp_coverage(days=7),
            "data_quality": self.check_data_quality(),
            "missing_runs_count": len(self.find_missing_runs()),
            "incomplete_races_count": len(self.find_incomplete_races()),
            "date_coverage": self.get_date_coverage(days=14),
        }


# Singleton instance
_tools: Optional[ClaudeTools] = None


def get_tools() -> ClaudeTools:
    """Get or create ClaudeTools singleton."""
    global _tools
    if _tools is None:
        _tools = ClaudeTools()
    return _tools
