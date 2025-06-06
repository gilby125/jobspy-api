package protocol

import (
	"fmt"
	"time"
)

// TaskStatus represents the status of a scraping task
type TaskStatus string

const (
	TaskStatusPending TaskStatus = "pending"
	TaskStatusRunning TaskStatus = "running"
	TaskStatusSuccess TaskStatus = "success"
	TaskStatusFailed  TaskStatus = "failed"
	TaskStatusPartial TaskStatus = "partial"
	TaskStatusTimeout TaskStatus = "timeout"
	TaskStatusRetry   TaskStatus = "retry"
)

// ScraperType represents the type of scraper
type ScraperType string

const (
	ScraperTypeIndeed       ScraperType = "indeed"
	ScraperTypeLinkedIn     ScraperType = "linkedin"
	ScraperTypeGlassdoor    ScraperType = "glassdoor"
	ScraperTypeZipRecruiter ScraperType = "ziprecruiter"
	ScraperTypeGoogle       ScraperType = "google"
)

// ScrapingTaskParams holds parameters for a scraping task
type ScrapingTaskParams struct {
	SearchTerm      string   `json:"search_term"`
	Location        string   `json:"location"`
	ResultsWanted   int      `json:"results_wanted"`
	JobType         *string  `json:"job_type,omitempty"`
	ExperienceLevel *string  `json:"experience_level,omitempty"`
	IsRemote        *bool    `json:"is_remote,omitempty"`
	SalaryMin       *int     `json:"salary_min,omitempty"`
	SalaryMax       *int     `json:"salary_max,omitempty"`
	Proxy           *string  `json:"proxy,omitempty"`
	UserAgent       *string  `json:"user_agent,omitempty"`
	DelayRange      []int    `json:"delay_range,omitempty"`
	PageLimit       int      `json:"page_limit"`
}

// ScrapingTask represents a task to be executed by a scraper
type ScrapingTask struct {
	TaskID      string              `json:"task_id"`
	ScraperType ScraperType         `json:"scraper_type"`
	Params      ScrapingTaskParams  `json:"params"`
	CreatedAt   string              `json:"created_at"`
	Timeout     int                 `json:"timeout"`
	RetryCount  int                 `json:"retry_count"`
	MaxRetries  int                 `json:"max_retries"`
	Priority    int                 `json:"priority"`
}

// JobData represents individual job data from scraping
type JobData struct {
	Title           string   `json:"title"`
	Company         string   `json:"company"`
	Location        string   `json:"location"`
	JobURL          string   `json:"job_url"`
	Description     string   `json:"description"`
	PostedDate      *string  `json:"posted_date,omitempty"`
	SalaryMin       *float64 `json:"salary_min,omitempty"`
	SalaryMax       *float64 `json:"salary_max,omitempty"`
	SalaryCurrency  string   `json:"salary_currency"`
	JobType         *string  `json:"job_type,omitempty"`
	ExperienceLevel *string  `json:"experience_level,omitempty"`
	IsRemote        bool     `json:"is_remote"`
	ApplyURL        *string  `json:"apply_url,omitempty"`
	EasyApply       bool     `json:"easy_apply"`
	CompanyLogo     *string  `json:"company_logo,omitempty"`
	JobHash         *string  `json:"job_hash,omitempty"`
	ExternalJobID   *string  `json:"external_job_id,omitempty"`
	Skills          []string `json:"skills,omitempty"`
	Benefits        []string `json:"benefits,omitempty"`
	Requirements    *string  `json:"requirements,omitempty"`
}

// ScrapingMetadata holds metadata about the scraping execution
type ScrapingMetadata struct {
	ProxyUsed             *string `json:"proxy_used,omitempty"`
	UserAgentUsed         *string `json:"user_agent_used,omitempty"`
	RequestsMade          int     `json:"requests_made"`
	PagesScraped          int     `json:"pages_scraped"`
	RateLimited           bool    `json:"rate_limited"`
	CaptchaEncountered    bool    `json:"captcha_encountered"`
	BlockedRequests       int     `json:"blocked_requests"`
	AverageResponseTime   float64 `json:"average_response_time"`
	MemoryUsageMB         float64 `json:"memory_usage_mb"`
	WorkerID              *string `json:"worker_id,omitempty"`
}

// ScrapingResult represents the result of a scraping task
type ScrapingResult struct {
	TaskID        string            `json:"task_id"`
	Status        TaskStatus        `json:"status"`
	ScraperType   ScraperType       `json:"scraper_type"`
	ExecutionTime float64           `json:"execution_time"`
	JobsFound     int               `json:"jobs_found"`
	JobsData      []JobData         `json:"jobs_data"`
	Metadata      ScrapingMetadata  `json:"metadata"`
	CompletedAt   string            `json:"completed_at"`
	Error         *string           `json:"error,omitempty"`
}

// HealthStatus represents the health status of a scraper worker
type HealthStatus struct {
	WorkerID                 string      `json:"worker_id"`
	ScraperType              ScraperType `json:"scraper_type"`
	Status                   string      `json:"status"` // healthy, degraded, unhealthy
	ActiveTasks              int         `json:"active_tasks"`
	CompletedTasksLastHour   int         `json:"completed_tasks_last_hour"`
	ErrorRateLastHour        float64     `json:"error_rate_last_hour"`
	MemoryUsageMB            float64     `json:"memory_usage_mb"`
	CPUUsagePercent          float64     `json:"cpu_usage_percent"`
	ProxyPoolSize            int         `json:"proxy_pool_size"`
	ProxySuccessRate         float64     `json:"proxy_success_rate"`
	LastSuccessfulScrape     string      `json:"last_successful_scrape"`
	Timestamp                string      `json:"timestamp"`
}

// ErrorReport represents an error report from a scraper
type ErrorReport struct {
	TaskID      string                 `json:"task_id"`
	ScraperType ScraperType            `json:"scraper_type"`
	Error       string                 `json:"error"`
	Metadata    map[string]interface{} `json:"metadata"`
	Timestamp   string                 `json:"timestamp"`
}

// Redis channel names for communication
const (
	ChannelScrapingTasks   = "scraping:tasks"
	ChannelScrapingResults = "scraping:results"
	ChannelHealthMonitor   = "scrapers:health"
	ChannelErrorReporting  = "scrapers:errors"
	ChannelWorkerCommands  = "scrapers:commands"
)

// GetTaskQueue returns the Redis queue name for a specific scraper type
func GetTaskQueue(scraperType ScraperType) string {
	return ChannelScrapingTasks + ":" + string(scraperType)
}

// GetHealthKey returns the Redis key for a worker's health status
func GetHealthKey(scraperType ScraperType, workerID string) string {
	return ChannelHealthMonitor + ":" + string(scraperType) + ":" + workerID
}

// GetHealthPattern returns the Redis pattern for all health keys of a scraper type
func GetHealthPattern(scraperType ScraperType) string {
	return ChannelHealthMonitor + ":" + string(scraperType) + ":*"
}

// Validate validates a scraping task
func (t *ScrapingTask) Validate() error {
	if t.TaskID == "" {
		return fmt.Errorf("task_id is required")
	}
	if t.ScraperType == "" {
		return fmt.Errorf("scraper_type is required")
	}
	if t.Params.SearchTerm == "" {
		return fmt.Errorf("search_term is required")
	}
	if t.Params.Location == "" {
		return fmt.Errorf("location is required")
	}
	if t.Params.ResultsWanted <= 0 {
		return fmt.Errorf("results_wanted must be greater than 0")
	}
	if t.Timeout <= 0 {
		return fmt.Errorf("timeout must be greater than 0")
	}
	return nil
}

// IsValidScraperType checks if a scraper type is valid
func IsValidScraperType(scraperType string) bool {
	validTypes := []ScraperType{
		ScraperTypeIndeed,
		ScraperTypeLinkedIn,
		ScraperTypeGlassdoor,
		ScraperTypeZipRecruiter,
		ScraperTypeGoogle,
	}
	
	for _, validType := range validTypes {
		if ScraperType(scraperType) == validType {
			return true
		}
	}
	return false
}

// NewScrapingResult creates a new scraping result with defaults
func NewScrapingResult(taskID string, scraperType ScraperType) *ScrapingResult {
	return &ScrapingResult{
		TaskID:        taskID,
		ScraperType:   scraperType,
		Status:        TaskStatusPending,
		JobsData:      make([]JobData, 0),
		CompletedAt:   time.Now().UTC().Format(time.RFC3339),
		Metadata: ScrapingMetadata{
			RequestsMade:        0,
			PagesScraped:        0,
			RateLimited:         false,
			CaptchaEncountered:  false,
			BlockedRequests:     0,
			AverageResponseTime: 0.0,
			MemoryUsageMB:       0.0,
		},
	}
}

// NewHealthStatus creates a new health status with defaults
func NewHealthStatus(workerID string, scraperType ScraperType) *HealthStatus {
	return &HealthStatus{
		WorkerID:                 workerID,
		ScraperType:              scraperType,
		Status:                   "healthy",
		ActiveTasks:              0,
		CompletedTasksLastHour:   0,
		ErrorRateLastHour:        0.0,
		MemoryUsageMB:            0.0,
		CPUUsagePercent:          0.0,
		ProxyPoolSize:            0,
		ProxySuccessRate:         100.0,
		LastSuccessfulScrape:     time.Now().UTC().Format(time.RFC3339),
		Timestamp:                time.Now().UTC().Format(time.RFC3339),
	}
}