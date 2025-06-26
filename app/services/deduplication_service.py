"""
Job deduplication service for preventing duplicate job postings.

This service implements intelligent job deduplication using:
1. Content hashing for exact matches
2. Fuzzy matching for similar jobs
3. Company + title normalization
4. Location-based similarity scoring
"""
import hashlib
import re
from typing import Dict, List, Optional, Tuple, Set
from datetime import datetime, date, timedelta
from difflib import SequenceMatcher
import logging

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func

from app.models.tracking_models import JobPosting, Company, JobSource

logger = logging.getLogger(__name__)


class JobDeduplicationService:
    """Service for detecting and handling duplicate job postings."""
    
    def __init__(self, similarity_threshold: float = 0.85):
        """
        Initialize deduplication service.
        
        Args:
            similarity_threshold: Minimum similarity score to consider jobs as duplicates (0.0-1.0)
        """
        self.similarity_threshold = similarity_threshold
        self.stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 
            'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'be', 
            'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 
            'would', 'should', 'could', 'can', 'may', 'might', 'must'
        }
    
    def generate_job_hash(self, job_data: Dict) -> str:
        """
        Generate a unique hash for a job posting based on normalized content.
        
        Args:
            job_data: Dictionary containing job posting data
            
        Returns:
            SHA-256 hash string for the job
        """
        # Normalize and combine key fields for hashing
        normalized_data = {
            'title': self._normalize_title(job_data.get('title', '')),
            'company': self._normalize_company_name(job_data.get('company', '')),
            'location': self._normalize_location(job_data.get('location', '')),
            'job_type': job_data.get('job_type', '').lower().strip(),
            'description_snippet': self._extract_description_snippet(
                job_data.get('description', '')
            )
        }
        
        # Create hash input string
        hash_input = '|'.join([
            normalized_data['title'],
            normalized_data['company'],
            normalized_data['location'],
            normalized_data['job_type'],
            normalized_data['description_snippet']
        ])
        
        # Generate SHA-256 hash
        return hashlib.sha256(hash_input.encode('utf-8')).hexdigest()
    
    def find_duplicate_jobs(
        self, 
        job_data: Dict, 
        db: Session,
        max_age_days: int = 90
    ) -> List[Tuple[JobPosting, float]]:
        """
        Find potential duplicate jobs for a given job posting.
        
        Args:
            job_data: Job data to check for duplicates
            db: Database session
            max_age_days: Maximum age of jobs to consider for duplicates
            
        Returns:
            List of tuples containing (JobPosting, similarity_score)
        """
        duplicates = []
        
        # 1. Check for exact hash matches first
        job_hash = self.generate_job_hash(job_data)
        exact_match = db.query(JobPosting).filter(
            JobPosting.job_hash == job_hash
        ).first()
        
        if exact_match:
            return [(exact_match, 1.0)]
        
        # 2. Find candidate jobs using fuzzy matching
        candidates = self._get_candidate_jobs(job_data, db, max_age_days)
        
        # 3. Calculate similarity scores for candidates
        for candidate in candidates:
            similarity_score = self._calculate_similarity_score(job_data, candidate)
            
            if similarity_score >= self.similarity_threshold:
                duplicates.append((candidate, similarity_score))
        
        # Sort by similarity score (highest first)
        duplicates.sort(key=lambda x: x[1], reverse=True)
        
        return duplicates
    
    def is_duplicate_job(self, job_data: Dict, db: Session) -> Tuple[bool, Optional[JobPosting]]:
        """
        Check if a job is a duplicate of an existing posting.
        
        Args:
            job_data: Job data to check
            db: Database session
            
        Returns:
            Tuple of (is_duplicate, existing_job_posting)
        """
        duplicates = self.find_duplicate_jobs(job_data, db)
        
        if duplicates:
            # Return the best match
            best_match = duplicates[0]
            return True, best_match[0]
        
        return False, None
    
    def merge_job_sources(
        self, 
        existing_job: JobPosting, 
        new_job_data: Dict, 
        source_site: str,
        db: Session
    ) -> JobPosting:
        """
        Merge a new job source with an existing job posting.
        
        Args:
            existing_job: Existing job posting
            new_job_data: New job data to merge
            source_site: Source site of the new job
            db: Database session
            
        Returns:
            Updated job posting
        """
        # Check if this source already exists
        existing_source = db.query(JobSource).filter(
            and_(
                JobSource.job_posting_id == existing_job.id,
                JobSource.source_site == source_site
            )
        ).first()
        
        if not existing_source:
            # Create new job source
            new_source = JobSource(
                job_posting_id=existing_job.id,
                source_site=source_site,
                external_job_id=new_job_data.get('job_id'),
                job_url=new_job_data.get('job_url', ''),
                post_date=self._parse_date(new_job_data.get('date_posted')),
                apply_url=new_job_data.get('job_url_direct'),
                easy_apply=new_job_data.get('easy_apply', False)
            )
            db.add(new_source)
        else:
            # Update existing source
            existing_source.job_url = new_job_data.get('job_url', existing_source.job_url)
            existing_source.post_date = self._parse_date(new_job_data.get('date_posted')) or existing_source.post_date
            existing_source.apply_url = new_job_data.get('job_url_direct') or existing_source.apply_url
            existing_source.updated_at = datetime.utcnow()
        
        # Update job posting metadata
        existing_job.last_seen_at = datetime.utcnow()
        existing_job.updated_at = datetime.utcnow()
        
        # Update job metrics
        if existing_job.job_metrics:
            existing_job.job_metrics.total_seen_count += 1
            existing_job.job_metrics.last_activity_date = date.today()
            existing_job.job_metrics.updated_at = datetime.utcnow()
        
        db.commit()
        logger.info(f"Merged job source {source_site} with existing job {existing_job.id}")
        
        return existing_job
    
    def _get_candidate_jobs(
        self, 
        job_data: Dict, 
        db: Session, 
        max_age_days: int
    ) -> List[JobPosting]:
        """
        Get candidate jobs for similarity comparison.
        
        Uses database queries to narrow down potential matches before expensive similarity calculations.
        """
        # Get normalized search terms
        normalized_title = self._normalize_title(job_data.get('title', ''))
        normalized_company = self._normalize_company_name(job_data.get('company', ''))
        
        # Extract key terms from title for broader matching
        title_terms = self._extract_key_terms(normalized_title)
        
        # Build query for candidates
        query = db.query(JobPosting).join(Company)
        
        # Date filter
        cutoff_date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        cutoff_date = cutoff_date - timedelta(days=max_age_days)
        query = query.filter(JobPosting.first_seen_at >= cutoff_date)
        
        # Company name similarity (exact or partial match)
        if normalized_company:
            query = query.filter(
                or_(
                    func.lower(Company.name).contains(normalized_company.lower()),
                    func.lower(Company.name).like(f'%{normalized_company.lower()}%')
                )
            )
        
        # Title term matching (at least one term must match)
        if title_terms:
            title_conditions = []
            for term in title_terms:
                title_conditions.append(
                    func.lower(JobPosting.title).contains(term.lower())
                )
            query = query.filter(or_(*title_conditions))
        
        # Limit results to prevent performance issues
        candidates = query.limit(100).all()
        
        logger.debug(f"Found {len(candidates)} candidate jobs for similarity comparison")
        return candidates
    
    def _calculate_similarity_score(self, job_data: Dict, existing_job: JobPosting) -> float:
        """
        Calculate similarity score between new job data and existing job posting.
        
        Uses weighted scoring across multiple dimensions:
        - Title similarity (40%)
        - Company similarity (30%) 
        - Location similarity (15%)
        - Job type similarity (10%)
        - Description similarity (5%)
        """
        scores = {}
        
        # Title similarity (40%)
        new_title = self._normalize_title(job_data.get('title', ''))
        existing_title = self._normalize_title(existing_job.title)
        scores['title'] = self._text_similarity(new_title, existing_title) * 0.4
        
        # Company similarity (30%)
        new_company = self._normalize_company_name(job_data.get('company', ''))
        existing_company = self._normalize_company_name(existing_job.company.name)
        scores['company'] = self._text_similarity(new_company, existing_company) * 0.3
        
        # Location similarity (15%)
        new_location = self._normalize_location(job_data.get('location', ''))
        existing_location = self._normalize_location(
            f"{existing_job.location.city}, {existing_job.location.state}" 
            if existing_job.location else ""
        )
        scores['location'] = self._text_similarity(new_location, existing_location) * 0.15
        
        # Job type similarity (10%)
        new_job_type = job_data.get('job_type', '').lower().strip()
        existing_job_type = existing_job.job_type.lower() if existing_job.job_type else ''
        scores['job_type'] = (1.0 if new_job_type == existing_job_type else 0.0) * 0.1
        
        # Description similarity (5%)
        new_desc_snippet = self._extract_description_snippet(job_data.get('description', ''))
        existing_desc_snippet = self._extract_description_snippet(existing_job.description or '')
        scores['description'] = self._text_similarity(new_desc_snippet, existing_desc_snippet) * 0.05
        
        total_score = sum(scores.values())
        
        logger.debug(f"Similarity scores: {scores}, Total: {total_score:.3f}")
        return total_score
    
    def _normalize_title(self, title: str) -> str:
        """Normalize job title for comparison."""
        if not title:
            return ""
        
        # Convert to lowercase and remove extra whitespace
        normalized = re.sub(r'\s+', ' ', title.lower().strip())
        
        # Remove common prefixes/suffixes that don't affect job similarity
        patterns = [
            r'\b(senior|sr\.?|junior|jr\.?|lead|principal|chief|head of)\s+',
            r'\s+(i{1,3}|iv|v|vi{1,3}|1|2|3|4|5)$',  # Roman numerals and numbers
            r'\s*[-–—]\s*\d+\s*(months?|years?)\s*experience\s*',
            r'\s*\([^)]*\)\s*',  # Remove parenthetical content
            r'\s*(remote|onsite|hybrid|work from home|wfh)\s*',
        ]
        
        for pattern in patterns:
            normalized = re.sub(pattern, ' ', normalized, flags=re.IGNORECASE)
        
        # Clean up extra spaces
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        
        return normalized
    
    def _normalize_company_name(self, company: str) -> str:
        """Normalize company name for comparison."""
        if not company:
            return ""
        
        # Convert to lowercase and remove extra whitespace
        normalized = re.sub(r'\s+', ' ', company.lower().strip())
        
        # Remove common company suffixes
        suffixes = [
            r'\s+(inc\.?|incorporated|corp\.?|corporation|ltd\.?|limited|llc|llp|lp|co\.?|company)\s*$'
        ]
        
        for suffix in suffixes:
            normalized = re.sub(suffix, '', normalized, flags=re.IGNORECASE)
        
        return normalized.strip()
    
    def _normalize_location(self, location: str) -> str:
        """Normalize location string for comparison."""
        if not location:
            return ""
        
        # Convert to lowercase and standardize separators
        normalized = location.lower().strip()
        normalized = re.sub(r'[,;|]', ',', normalized)
        normalized = re.sub(r'\s+', ' ', normalized)
        
        # Remove common location patterns that don't affect similarity
        patterns = [
            r'\s*(remote|work from home|wfh)\s*',
            r'\s*\([^)]*\)\s*',  # Remove parenthetical content
            r'\s*(usa|united states|us)\s*$',
        ]
        
        for pattern in patterns:
            normalized = re.sub(pattern, '', normalized, flags=re.IGNORECASE)
        
        return normalized.strip()
    
    def _extract_description_snippet(self, description: str, max_length: int = 200) -> str:
        """Extract key snippet from job description for comparison."""
        if not description:
            return ""
        
        # Remove HTML tags and normalize whitespace
        clean_desc = re.sub(r'<[^>]+>', ' ', description)
        clean_desc = re.sub(r'\s+', ' ', clean_desc).strip()
        
        # Extract first few sentences or up to max_length
        if len(clean_desc) <= max_length:
            return clean_desc.lower()
        
        # Try to break at sentence boundaries
        sentences = re.split(r'[.!?]+', clean_desc)
        snippet = ""
        for sentence in sentences:
            if len(snippet + sentence) <= max_length:
                snippet += sentence + "."
            else:
                break
        
        return snippet.lower().strip()
    
    def _extract_key_terms(self, text: str) -> Set[str]:
        """Extract key terms from text for matching."""
        if not text:
            return set()
        
        # Split into words and remove stop words
        words = re.findall(r'\b\w+\b', text.lower())
        key_terms = {word for word in words if len(word) > 2 and word not in self.stop_words}
        
        return key_terms
    
    def _text_similarity(self, text1: str, text2: str) -> float:
        """Calculate text similarity using sequence matching."""
        if not text1 or not text2:
            return 0.0
        
        return SequenceMatcher(None, text1, text2).ratio()
    
    def _parse_date(self, date_str: Optional[str]) -> Optional[date]:
        """Parse date string to date object."""
        if not date_str:
            return None
        
        try:
            # Handle various date formats
            if isinstance(date_str, date):
                return date_str
            
            # Try common formats
            for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%Y-%m-%d %H:%M:%S']:
                try:
                    parsed = datetime.strptime(str(date_str), fmt).date()
                    # Validate the parsed date is reasonable
                    if parsed.year < 1900 or parsed.year > 2030:
                        continue
                    return parsed
                except (ValueError, OverflowError):
                    continue
            
            logger.warning(f"Could not parse date: {date_str}")
            return None
        except Exception as e:
            logger.error(f"Error parsing date {date_str}: {e}")
            return None


# Global service instance
deduplication_service = JobDeduplicationService()