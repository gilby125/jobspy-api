import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.models.admin_models import SearchLog


class LogService:
    """Service for reading and managing application logs"""
    
    def __init__(self, db: Session):
        self.db = db
        self.logger = logging.getLogger(__name__)
        self.log_dir = Path("logs")
        
    async def get_recent_logs(self, limit: int = 100, level: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get recent application logs from log files"""
        logs = []
        
        # Read from the main log file
        log_file = self.log_dir / "app.log"
        if log_file.exists():
            try:
                with open(log_file, 'r') as f:
                    lines = f.readlines()
                    
                # Take the last N lines and parse them
                recent_lines = lines[-limit*2:] if len(lines) > limit*2 else lines
                
                for line in reversed(recent_lines):
                    line = line.strip()
                    if not line:
                        continue
                        
                    log_entry = self._parse_log_line(line)
                    if log_entry and (not level or log_entry.get('level') == level.upper()):
                        logs.append(log_entry)
                        
                    if len(logs) >= limit:
                        break
                        
            except Exception as e:
                self.logger.error(f"Error reading log file: {e}")
                # Add error as a log entry
                logs.append({
                    'timestamp': datetime.now().isoformat(),
                    'level': 'ERROR',
                    'message': f'Failed to read log file: {str(e)}',
                    'logger': 'log_service'
                })
        
        # If no logs from file, add some system status logs
        if not logs:
            logs.extend(await self._get_system_status_logs())
            
        return logs[:limit]
    
    async def get_search_logs(self, search_id: Optional[str] = None, 
                            level: Optional[str] = None, 
                            limit: int = 100) -> List[SearchLog]:
        """Get search-specific logs from database and log files"""
        logs = []
        
        # Get logs from database (scraping runs)
        try:
            query = text("""
                SELECT 
                    id::text as search_id,
                    source_platform,
                    search_terms,
                    locations,
                    start_time as timestamp,
                    status,
                    jobs_found,
                    jobs_processed,
                    error_count,
                    error_details
                FROM scraping_runs 
                WHERE ($1 IS NULL OR id::text = $1)
                ORDER BY start_time DESC 
                LIMIT $2
            """)
            
            result = self.db.execute(query, (search_id, limit))
            
            for row in result:
                level_map = {
                    'running': 'INFO',
                    'completed': 'INFO', 
                    'failed': 'ERROR',
                    'cancelled': 'WARN'
                }
                
                log_level = level_map.get(row.status, 'INFO')
                if level and log_level != level.upper():
                    continue
                    
                message = f"Search: {', '.join(row.search_terms)} in {', '.join(row.locations)} - Status: {row.status}"
                if row.jobs_found:
                    message += f" - Found {row.jobs_found} jobs"
                if row.error_details:
                    message += f" - Error: {row.error_details}"
                
                logs.append(SearchLog(
                    id=f"db_{row.search_id}_{int(row.timestamp.timestamp())}",
                    search_id=row.search_id,
                    timestamp=row.timestamp,
                    level=log_level,
                    message=message,
                    details={"logger": "job_service"}
                ))
                
        except Exception as e:
            self.logger.error(f"Error getting database logs: {e}")
            # Add error log
            logs.append(SearchLog(
                id=f"error_{int(datetime.now().timestamp())}",
                search_id=search_id or "unknown",
                timestamp=datetime.now(),
                level="ERROR",
                message=f"Failed to retrieve database logs: {str(e)}",
                details={"logger": "log_service"}
            ))
        
        # Add recent application logs if search_id is None (general logs request)
        if not search_id:
            recent_logs = await self.get_recent_logs(limit//2, level)
            for i, log_data in enumerate(recent_logs):
                timestamp = datetime.fromisoformat(log_data['timestamp']) if isinstance(log_data['timestamp'], str) else log_data['timestamp']
                logs.append(SearchLog(
                    id=f"sys_{int(timestamp.timestamp())}_{i}",
                    search_id="system",
                    timestamp=timestamp,
                    level=log_data['level'],
                    message=log_data['message'],
                    details={"logger": log_data.get('logger', 'system')}
                ))
        
        # Sort by timestamp descending and return limited results
        logs.sort(key=lambda x: x.timestamp, reverse=True)
        return logs[:limit]
    
    def _parse_log_line(self, line: str) -> Optional[Dict[str, Any]]:
        """Parse a log line into structured data"""
        try:
            # Expected format: "2025-01-07 10:30:45,123 - logger_name - LEVEL - message"
            parts = line.split(' - ', 3)
            if len(parts) >= 4:
                timestamp_str = parts[0]
                logger_name = parts[1] 
                level = parts[2]
                message = parts[3]
                
                # Parse timestamp
                try:
                    # Handle both formats: with and without microseconds
                    if ',' in timestamp_str:
                        dt = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S,%f")
                    else:
                        dt = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    dt = datetime.now()
                
                return {
                    'timestamp': dt.isoformat(),
                    'level': level,
                    'message': message,
                    'logger': logger_name
                }
        except Exception:
            # If parsing fails, treat entire line as message
            return {
                'timestamp': datetime.now().isoformat(),
                'level': 'INFO',
                'message': line,
                'logger': 'unknown'
            }
        
        return None
    
    async def _get_system_status_logs(self) -> List[Dict[str, Any]]:
        """Generate system status logs when no file logs are available"""
        logs = []
        now = datetime.now()
        
        # Check system health
        try:
            # Database connectivity
            self.db.execute(text("SELECT 1"))
            logs.append({
                'timestamp': now.isoformat(),
                'level': 'INFO',
                'message': 'Database connection healthy',
                'logger': 'health_check'
            })
        except Exception as e:
            logs.append({
                'timestamp': now.isoformat(), 
                'level': 'ERROR',
                'message': f'Database connection failed: {str(e)}',
                'logger': 'health_check'
            })
        
        # Check recent activity
        try:
            result = self.db.execute(text("""
                SELECT COUNT(*) as count 
                FROM scraping_runs 
                WHERE start_time > NOW() - INTERVAL '1 hour'
            """))
            count = result.scalar()
            
            if count > 0:
                logs.append({
                    'timestamp': now.isoformat(),
                    'level': 'INFO', 
                    'message': f'Found {count} scraping runs in the last hour',
                    'logger': 'activity_monitor'
                })
            else:
                logs.append({
                    'timestamp': now.isoformat(),
                    'level': 'INFO',
                    'message': 'No recent scraping activity detected',
                    'logger': 'activity_monitor'
                })
                
        except Exception as e:
            logs.append({
                'timestamp': now.isoformat(),
                'level': 'WARN',
                'message': f'Could not check recent activity: {str(e)}',
                'logger': 'activity_monitor'
            })
        
        return logs
    
    async def add_search_log(self, search_id: str, level: str, message: str, logger: str = "system"):
        """Add a search log entry to the database"""
        try:
            # For now, we'll log it to the application logger
            app_logger = logging.getLogger(logger)
            log_method = getattr(app_logger, level.lower(), app_logger.info)
            log_method(f"[Search {search_id}] {message}")
            
        except Exception as e:
            self.logger.error(f"Failed to add search log: {e}")