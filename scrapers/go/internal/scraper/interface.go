package scraper

import (
	"context"
	"fmt"
	"net/http"
	"time"

	"github.com/jobspy/scrapers/internal/protocol"
)

// Scraper defines the interface for all job scrapers
type Scraper interface {
	// GetName returns the name of the scraper
	GetName() string
	
	// GetType returns the scraper type
	GetType() protocol.ScraperType
	
	// Configure sets up the scraper with given parameters
	Configure(config ScraperConfig) error
	
	// ScrapeJobs performs the actual job scraping
	ScrapeJobs(ctx context.Context, params protocol.ScrapingTaskParams) (*protocol.ScrapingResult, error)
	
	// ValidateParams validates scraping parameters for this scraper
	ValidateParams(params protocol.ScrapingTaskParams) error
	
	// GetHealthStatus returns current health status
	GetHealthStatus() *protocol.HealthStatus
	
	// Close cleans up resources
	Close() error
}

// ScraperConfig holds configuration for a scraper
type ScraperConfig struct {
	// Basic configuration
	WorkerID    string
	Region      string
	BaseURL     string
	MaxPages    int
	PageSize    int
	Timeout     time.Duration
	
	// Anti-detection configuration
	ProxyPool           []string
	UserAgents          []string
	MinDelay            time.Duration
	MaxDelay            time.Duration
	RotateProxies       bool
	RotateUserAgents    bool
	StealthMode         bool
	BrowserMode         bool
	
	// Rate limiting
	RateLimitRPM        int
	ConcurrentRequests  int
	
	// HTTP client configuration
	MaxIdleConns        int
	MaxConnsPerHost     int
	IdleConnTimeout     time.Duration
	TLSHandshakeTimeout time.Duration
	ResponseTimeout     time.Duration
	
	// Monitoring
	MetricsEnabled      bool
	
	// Site-specific configuration
	SiteConfig          map[string]interface{}
}

// ScrapingMetrics holds metrics for a scraping session
type ScrapingMetrics struct {
	StartTime           time.Time
	EndTime             time.Time
	RequestsMade        int
	PagesScraped        int
	JobsFound           int
	RateLimitHits       int
	CaptchaEncounters   int
	BlockedRequests     int
	ProxyFailures       int
	TotalResponseTime   time.Duration
	AverageResponseTime time.Duration
	MemoryUsage         float64
	ProxyUsed           string
	UserAgentUsed       string
	ErrorsEncountered   []string
}

// HTTPClientInterface defines the interface for HTTP clients
type HTTPClientInterface interface {
	Do(req *http.Request) (*http.Response, error)
	Get(url string) (*http.Response, error)
	Post(url, contentType string, body interface{}) (*http.Response, error)
}

// ProxyManager handles proxy rotation and health
type ProxyManager interface {
	GetProxy() (string, error)
	MarkProxyFailed(proxy string)
	MarkProxySuccess(proxy string)
	GetHealthyProxies() []string
	GetProxyStats() map[string]ProxyStats
}

// ProxyStats holds statistics for a proxy
type ProxyStats struct {
	URL           string
	TotalRequests int
	SuccessCount  int
	FailureCount  int
	SuccessRate   float64
	LastUsed      time.Time
	LastSuccess   time.Time
	LastFailure   time.Time
	IsHealthy     bool
}

// UserAgentManager handles user agent rotation
type UserAgentManager interface {
	GetUserAgent() string
	GetRandomUserAgent() string
	AddUserAgent(ua string)
	GetStats() UserAgentStats
}

// UserAgentStats holds user agent statistics
type UserAgentStats struct {
	TotalUserAgents int
	CurrentIndex    int
	LastRotated     time.Time
}

// RateLimiter manages request rate limiting
type RateLimiter interface {
	Wait(ctx context.Context) error
	Allow() bool
	SetRate(requestsPerMinute int)
	GetStats() RateLimiterStats
}

// RateLimiterStats holds rate limiter statistics
type RateLimiterStats struct {
	RequestsPerMinute int
	CurrentRequests   int
	LastRequest       time.Time
	WaitTime          time.Duration
}

// JobParser parses job data from HTML/JSON responses
type JobParser interface {
	ParseJobList(content []byte, baseURL string) ([]protocol.JobData, error)
	ParseJobDetails(content []byte, jobURL string) (*protocol.JobData, error)
	ExtractPaginationInfo(content []byte) (PaginationInfo, error)
}

// PaginationInfo holds pagination information
type PaginationInfo struct {
	CurrentPage   int
	TotalPages    int
	NextPageURL   string
	HasNextPage   bool
	ResultsPerPage int
	TotalResults  int
}

// ScraperFactory creates scrapers based on type
type ScraperFactory interface {
	CreateScraper(scraperType protocol.ScraperType, config ScraperConfig) (Scraper, error)
	GetSupportedTypes() []protocol.ScraperType
}

// ContentExtractor extracts content from web pages
type ContentExtractor interface {
	ExtractContent(url string, selectors map[string]string) (map[string]string, error)
	ExtractWithContext(ctx context.Context, url string, selectors map[string]string) (map[string]string, error)
}

// AntiDetectionManager handles anti-detection measures
type AntiDetectionManager interface {
	GetHTTPClient() HTTPClientInterface
	ModifyRequest(req *http.Request) error
	ShouldRetry(resp *http.Response, err error) bool
	HandleCaptcha(resp *http.Response) error
	SimulateHumanBehavior(ctx context.Context) error
}

// HealthMonitor monitors scraper health
type HealthMonitor interface {
	UpdateHealth(status *protocol.HealthStatus)
	GetHealth() *protocol.HealthStatus
	ReportError(error string, metadata map[string]interface{})
	ReportSuccess(jobsFound int, duration time.Duration)
	IsHealthy() bool
}

// ValidationError represents a parameter validation error
type ValidationError struct {
	Field   string
	Value   interface{}
	Message string
}

func (e ValidationError) Error() string {
	return fmt.Sprintf("validation error for field '%s': %s", e.Field, e.Message)
}

// ScrapingError represents an error during scraping
type ScrapingError struct {
	Type      string
	Message   string
	URL       string
	StatusCode int
	Retryable bool
	Metadata  map[string]interface{}
}

func (e ScrapingError) Error() string {
	return fmt.Sprintf("scraping error [%s]: %s", e.Type, e.Message)
}

// Common error types
const (
	ErrorTypeNetwork     = "network"
	ErrorTypeParsing     = "parsing"
	ErrorTypeRateLimit   = "rate_limit"
	ErrorTypeCaptcha     = "captcha"
	ErrorTypeBlocked     = "blocked"
	ErrorTypeTimeout     = "timeout"
	ErrorTypeValidation  = "validation"
	ErrorTypeInternal    = "internal"
)