"""
SQLite Database Module for YouTube Content Detector
Handles storage of analysis history and statistics
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


class AnalysisDatabase:
    """Manages SQLite database for analysis history"""

    def __init__(self, db_path: str = "data/analysis_history.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_database()

    def _init_database(self):
        """Initialize database tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Analysis runs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS analysis_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                file_name TEXT NOT NULL,
                total_videos INTEGER,
                reupload_count INTEGER,
                reupload_percent REAL,
                cluster_count INTEGER,
                audio_threshold REAL,
                video_threshold REAL,
                combined_threshold REAL,
                gpu_enabled BOOLEAN,
                processing_time_seconds REAL,
                results_summary TEXT
            )
        """)

        # Individual video results table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS video_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER,
                video_id TEXT,
                channel_name TEXT,
                title TEXT,
                is_reupload BOOLEAN,
                cluster_id INTEGER,
                similarity_score REAL,
                FOREIGN KEY (run_id) REFERENCES analysis_runs(id)
            )
        """)

        # Create indexes for faster queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_run_created
            ON analysis_runs(created_at DESC)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_video_run
            ON video_results(run_id)
        """)

        conn.commit()
        conn.close()

    def save_analysis(self, analysis_data: Dict) -> int:
        """
        Save analysis results to database
        Returns: run_id
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Insert analysis run
        cursor.execute("""
            INSERT INTO analysis_runs (
                file_name, total_videos, reupload_count, reupload_percent,
                cluster_count, audio_threshold, video_threshold,
                combined_threshold, gpu_enabled, processing_time_seconds,
                results_summary
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            analysis_data.get('file_name'),
            analysis_data.get('total_videos'),
            analysis_data.get('reupload_count'),
            analysis_data.get('reupload_percent'),
            analysis_data.get('cluster_count'),
            analysis_data.get('audio_threshold'),
            analysis_data.get('video_threshold'),
            analysis_data.get('combined_threshold'),
            analysis_data.get('gpu_enabled'),
            analysis_data.get('processing_time_seconds'),
            json.dumps(analysis_data.get('summary', {}))
        ))

        run_id = cursor.lastrowid

        # Insert video results if available
        if 'videos' in analysis_data:
            for video in analysis_data['videos']:
                cursor.execute("""
                    INSERT INTO video_results (
                        run_id, video_id, channel_name, title,
                        is_reupload, cluster_id, similarity_score
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    run_id,
                    video.get('video_id'),
                    video.get('channel_name'),
                    video.get('title'),
                    video.get('is_reupload'),
                    video.get('cluster_id'),
                    video.get('similarity_score')
                ))

        conn.commit()
        conn.close()

        return run_id

    def get_history(self, limit: int = 50, offset: int = 0) -> List[Dict]:
        """Get analysis history with pagination"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                id, created_at, file_name, total_videos,
                reupload_count, reupload_percent, cluster_count,
                audio_threshold, video_threshold, combined_threshold,
                gpu_enabled, processing_time_seconds
            FROM analysis_runs
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """, (limit, offset))

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def get_analysis_by_id(self, run_id: int) -> Optional[Dict]:
        """Get specific analysis with video details"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get run info
        cursor.execute("""
            SELECT * FROM analysis_runs WHERE id = ?
        """, (run_id,))

        run = cursor.fetchone()
        if not run:
            conn.close()
            return None

        result = dict(run)

        # Get video results
        cursor.execute("""
            SELECT * FROM video_results WHERE run_id = ?
        """, (run_id,))

        result['videos'] = [dict(row) for row in cursor.fetchall()]

        conn.close()
        return result

    def delete_analysis(self, run_id: int) -> bool:
        """Delete analysis and its video results"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("DELETE FROM video_results WHERE run_id = ?", (run_id,))
        cursor.execute("DELETE FROM analysis_runs WHERE id = ?", (run_id,))

        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()

        return deleted

    def get_statistics(self) -> Dict:
        """Get overall statistics"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Overall stats
        cursor.execute("""
            SELECT
                COUNT(*) as total_runs,
                SUM(total_videos) as total_videos_analyzed,
                SUM(reupload_count) as total_reuploads_found,
                AVG(reupload_percent) as avg_reupload_rate,
                AVG(processing_time_seconds) as avg_processing_time
            FROM analysis_runs
        """)

        overall = dict(cursor.fetchone())

        # Recent runs (last 30 days trend)
        cursor.execute("""
            SELECT
                DATE(created_at) as date,
                COUNT(*) as runs,
                AVG(reupload_percent) as avg_rate
            FROM analysis_runs
            WHERE created_at >= datetime('now', '-30 days')
            GROUP BY DATE(created_at)
            ORDER BY date DESC
        """)

        trend = [dict(row) for row in cursor.fetchall()]

        # Top channels with most reuploads
        cursor.execute("""
            SELECT
                channel_name,
                COUNT(*) as reupload_count
            FROM video_results
            WHERE is_reupload = 1
            GROUP BY channel_name
            ORDER BY reupload_count DESC
            LIMIT 10
        """)

        top_channels = [dict(row) for row in cursor.fetchall()]

        conn.close()

        return {
            'overall': overall,
            'trend': trend,
            'top_channels': top_channels
        }

    def search_history(self, query: str) -> List[Dict]:
        """Search history by file name or date"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                id, created_at, file_name, total_videos,
                reupload_count, reupload_percent
            FROM analysis_runs
            WHERE file_name LIKE ?
            ORDER BY created_at DESC
            LIMIT 50
        """, (f'%{query}%',))

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]
