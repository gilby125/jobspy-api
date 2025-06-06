package jobspy_client

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"

	"github.com/sirupsen/logrus"

	"github.com/jobspy/scrapers/internal/protocol"
	"github.com/jobspy/scrapers/internal/scraper"
)

// JobSpyAPIClient implements the Scraper interface by calling JobSpy API
type JobSpyAPIClient struct {
	config       scraper.ScraperConfig
	logger       *logrus.Logger
	httpClient   *http.Client
	metrics      *scraper.ScrapingMetrics
	healthStatus *protocol.HealthStatus
	apiBaseURL   string
}

// JobSpyRequest represents the request format for JobSpy API
type JobSpyRequest struct {
	SiteName             []string `json:"site_name"`
	SearchTerm           string   `json:"search_term,omitempty"`
	Location             string   `json:"location,omitempty"`
	Distance             int      `json:"distance,omitempty"`
	JobType              string   `json:"job_type,omitempty"`
	IsRemote             *bool    `json:"is_remote,omitempty"`
	ResultsWanted        int      `json:"results_wanted,omitempty"`
	HoursOld             *int     `json:"hours_old,omitempty"`
	EasyApply            *bool    `json:"easy_apply,omitempty"`
	DescriptionFormat    string   `json:"description_format,omitempty"`
	Verbose              int      `json:"verbose,omitempty"`
	CountryIndeed        string   `json:"country_indeed,omitempty"`
	EnforceAnnualSalary  bool     `json:"enforce_annual_salary,omitempty"`
}

// JobSpyResponse represents the response format from JobSpy API
type JobSpyResponse struct {
	Count int                      `json:"count"`
	Jobs  []map[string]interface{} `json:"jobs"`
	Cached bool                    `json:"cached"`
}

// NewJobSpyAPIClient creates a new JobSpy API client
func NewJobSpyAPIClient(config scraper.ScraperConfig, logger *logrus.Logger) *JobSpyAPIClient {
	// Create HTTP client with timeouts
	httpClient := &http.Client{
		Timeout: config.ResponseTimeout,
		Transport: &http.Transport{
			MaxIdleConns:        config.MaxIdleConns,
			MaxConnsPerHost:     config.MaxConnsPerHost,
			IdleConnTimeout:     config.IdleConnTimeout,
			TLSHandshakeTimeout: config.TLSHandshakeTimeout,
		},
	}

	// Default to local JobSpy API
	apiBaseURL := config.BaseURL
	if apiBaseURL == "" {
		apiBaseURL = "http://localhost:8000"
	}

	return &JobSpyAPIClient{
		config:       config,
		logger:       logger,
		httpClient:   httpClient,
		metrics:      &scraper.ScrapingMetrics{},
		healthStatus: protocol.NewHealthStatus(config.WorkerID, protocol.ScraperType("jobspy")),
		apiBaseURL:   apiBaseURL,
	}
}

// GetName returns the scraper name
func (c *JobSpyAPIClient) GetName() string {
	return "JobSpy API Client"
}

// GetType returns the scraper type
func (c *JobSpyAPIClient) GetType() protocol.ScraperType {
	return protocol.ScraperType("jobspy")
}

// Configure sets up the client
func (c *JobSpyAPIClient) Configure(config scraper.ScraperConfig) error {
	c.config = config
	c.logger.WithFields(logrus.Fields{
		"worker_id":    config.WorkerID,
		"api_base_url": c.apiBaseURL,
	}).Info("JobSpy API client configured")
	return nil
}

// ValidateParams validates scraping parameters
func (c *JobSpyAPIClient) ValidateParams(params protocol.ScrapingTaskParams) error {
	if params.SearchTerm == "" {
		return scraper.ValidationError{
			Field:   "search_term",
			Value:   params.SearchTerm,
			Message: "search term is required",
		}
	}

	if params.Location == "" {
		return scraper.ValidationError{
			Field:   "location",
			Value:   params.Location,
			Message: "location is required",
		}
	}

	if params.ResultsWanted <= 0 || params.ResultsWanted > 1000 {
		return scraper.ValidationError{
			Field:   "results_wanted",
			Value:   params.ResultsWanted,
			Message: "results_wanted must be between 1 and 1000",
		}
	}

	return nil
}

// ScrapeJobs performs the actual job scraping by calling JobSpy API
func (c *JobSpyAPIClient) ScrapeJobs(ctx context.Context, params protocol.ScrapingTaskParams) (*protocol.ScrapingResult, error) {
	// Initialize result
	result := protocol.NewScrapingResult("", protocol.ScraperType("jobspy"))
	result.Status = protocol.TaskStatusRunning

	// Initialize metrics
	c.metrics.StartTime = time.Now()
	c.metrics.RequestsMade = 0
	c.metrics.JobsFound = 0

	c.logger.WithFields(logrus.Fields{
		"search_term":    params.SearchTerm,
		"location":       params.Location,
		"results_wanted": params.ResultsWanted,
	}).Info("Starting JobSpy API job scraping")

	// Validate parameters
	if err := c.ValidateParams(params); err != nil {
		result.Status = protocol.TaskStatusFailed
		errorMsg := fmt.Sprintf("Parameter validation failed: %v", err)
		result.Error = &errorMsg
		return result, err
	}

	// Convert task params to JobSpy API request
	jobspyRequest := c.convertToJobSpyRequest(params)

	// Make API call
	jobs, err := c.callJobSpyAPI(ctx, jobspyRequest)
	if err != nil {
		result.Status = protocol.TaskStatusFailed
		errorMsg := fmt.Sprintf("JobSpy API call failed: %v", err)
		result.Error = &errorMsg
		return result, err
	}

	// Convert response to protocol format
	protocolJobs := c.convertToProtocolJobs(jobs)

	// Finalize metrics and result
	c.metrics.EndTime = time.Now()
	c.metrics.JobsFound = len(protocolJobs)

	if c.metrics.RequestsMade > 0 {
		c.metrics.AverageResponseTime = c.metrics.TotalResponseTime / time.Duration(c.metrics.RequestsMade)
	}

	result.JobsFound = len(protocolJobs)
	result.JobsData = protocolJobs
	result.ExecutionTime = c.metrics.EndTime.Sub(c.metrics.StartTime).Seconds()
	result.Status = protocol.TaskStatusSuccess
	result.CompletedAt = time.Now().UTC().Format(time.RFC3339)

	// Update metadata
	result.Metadata = protocol.ScrapingMetadata{
		RequestsMade:        c.metrics.RequestsMade,
		PagesScraped:        1, // JobSpy API handles pagination internally
		RateLimited:         false,
		CaptchaEncountered:  false,
		BlockedRequests:     0,
		AverageResponseTime: c.metrics.AverageResponseTime.Seconds(),
		WorkerID:            &c.config.WorkerID,
	}

	c.logger.WithFields(logrus.Fields{
		"jobs_found":     len(protocolJobs),
		"execution_time": result.ExecutionTime,
		"api_url":        c.apiBaseURL,
	}).Info("JobSpy API scraping completed successfully")

	return result, nil
}

// convertToJobSpyRequest converts protocol params to JobSpy API request format
func (c *JobSpyAPIClient) convertToJobSpyRequest(params protocol.ScrapingTaskParams) JobSpyRequest {
	request := JobSpyRequest{
		SiteName:            []string{"indeed", "linkedin", "glassdoor", "zip_recruiter", "google"},
		SearchTerm:          params.SearchTerm,
		Location:            params.Location,
		Distance:            50, // Default distance
		ResultsWanted:       params.ResultsWanted,
		DescriptionFormat:   "markdown",
		Verbose:             2,
		CountryIndeed:       "USA",
		EnforceAnnualSalary: false,
	}

	// Set optional parameters if provided
	if params.JobType != nil {
		request.JobType = *params.JobType
	}

	if params.IsRemote != nil {
		request.IsRemote = params.IsRemote
	}

	if params.SalaryMin != nil && *params.SalaryMin > 0 {
		// JobSpy doesn't have direct salary filtering in API
		// This could be handled in post-processing
	}

	return request
}

// callJobSpyAPI makes the actual HTTP call to JobSpy API
func (c *JobSpyAPIClient) callJobSpyAPI(ctx context.Context, request JobSpyRequest) ([]map[string]interface{}, error) {
	startTime := time.Now()

	// Marshal request to JSON
	requestBody, err := json.Marshal(request)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal request: %w", err)
	}

	// Create HTTP request
	apiURL := fmt.Sprintf("%s/api/v1/search_jobs", c.apiBaseURL)
	req, err := http.NewRequestWithContext(ctx, "POST", apiURL, bytes.NewBuffer(requestBody))
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	// Set headers
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Accept", "application/json")
	
	// Add API key if configured
	if len(c.config.UserAgents) > 0 {
		// Use UserAgents config field to pass API key for now
		req.Header.Set("x-api-key", c.config.UserAgents[0])
	}

	// Make request
	resp, err := c.httpClient.Do(req)
	if err != nil {
		c.metrics.BlockedRequests++
		return nil, fmt.Errorf("HTTP request failed: %w", err)
	}
	defer resp.Body.Close()

	// Update metrics
	c.metrics.RequestsMade++
	c.metrics.TotalResponseTime += time.Since(startTime)

	// Check response status
	if resp.StatusCode != 200 {
		if resp.StatusCode == 429 {
			c.metrics.RateLimitHits++
			return nil, scraper.ScrapingError{
				Type:       scraper.ErrorTypeRateLimit,
				Message:    "Rate limited by JobSpy API",
				StatusCode: resp.StatusCode,
				URL:        apiURL,
				Retryable:  true,
			}
		}

		if resp.StatusCode >= 400 {
			c.metrics.BlockedRequests++
			return nil, scraper.ScrapingError{
				Type:       scraper.ErrorTypeBlocked,
				Message:    fmt.Sprintf("Request failed with status %d", resp.StatusCode),
				StatusCode: resp.StatusCode,
				URL:        apiURL,
				Retryable:  resp.StatusCode >= 500,
			}
		}
	}

	// Read response body
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read response body: %w", err)
	}

	// Parse JSON response
	var jobspyResponse JobSpyResponse
	if err := json.Unmarshal(body, &jobspyResponse); err != nil {
		return nil, fmt.Errorf("failed to parse JSON response: %w", err)
	}

	c.logger.WithFields(logrus.Fields{
		"api_url":      apiURL,
		"jobs_count":   jobspyResponse.Count,
		"cached":       jobspyResponse.Cached,
		"status_code":  resp.StatusCode,
		"duration":     time.Since(startTime),
	}).Debug("JobSpy API call completed")

	return jobspyResponse.Jobs, nil
}

// convertToProtocolJobs converts JobSpy API response to protocol format
func (c *JobSpyAPIClient) convertToProtocolJobs(jobs []map[string]interface{}) []protocol.JobData {
	var protocolJobs []protocol.JobData

	for _, job := range jobs {
		protocolJob := protocol.JobData{
			SalaryCurrency: "USD",
			IsRemote:       false,
			EasyApply:      false,
			Skills:         []string{},
			Benefits:       []string{},
		}

		// Extract fields with type checking
		if title, ok := job["TITLE"].(string); ok {
			protocolJob.Title = title
		}

		if company, ok := job["COMPANY"].(string); ok {
			protocolJob.Company = company
		}

		if location, ok := job["LOCATION"].(string); ok {
			protocolJob.Location = location
		}

		if jobURL, ok := job["JOB_URL"].(string); ok {
			protocolJob.JobURL = jobURL
		}

		if description, ok := job["DESCRIPTION"].(string); ok {
			protocolJob.Description = description
		}

		if datePosted, ok := job["DATE_POSTED"].(string); ok {
			protocolJob.PostedDate = &datePosted
		}

		if minAmount, ok := job["MIN_AMOUNT"].(float64); ok {
			protocolJob.SalaryMin = &minAmount
		}

		if maxAmount, ok := job["MAX_AMOUNT"].(float64); ok {
			protocolJob.SalaryMax = &maxAmount
		}

		if currency, ok := job["CURRENCY"].(string); ok {
			protocolJob.SalaryCurrency = currency
		}

		if jobType, ok := job["JOB_TYPE"].(string); ok {
			protocolJob.JobType = &jobType
		}

		if isRemote, ok := job["IS_REMOTE"].(bool); ok {
			protocolJob.IsRemote = isRemote
		}

		if applyURL, ok := job["JOB_URL_DIRECT"].(string); ok {
			protocolJob.ApplyURL = &applyURL
		}

		if easyApply, ok := job["EASY_APPLY"].(bool); ok {
			protocolJob.EasyApply = easyApply
		}

		if companyLogo, ok := job["COMPANY_LOGO"].(string); ok {
			protocolJob.CompanyLogo = &companyLogo
		}

		protocolJobs = append(protocolJobs, protocolJob)
	}

	return protocolJobs
}

// GetHealthStatus returns current health status
func (c *JobSpyAPIClient) GetHealthStatus() *protocol.HealthStatus {
	c.healthStatus.Timestamp = time.Now().UTC().Format(time.RFC3339)
	c.healthStatus.MemoryUsageMB = c.metrics.MemoryUsage

	// Determine health based on recent performance
	if c.metrics.BlockedRequests > c.metrics.RequestsMade/2 {
		c.healthStatus.Status = "unhealthy"
	} else if c.metrics.RateLimitHits > 0 {
		c.healthStatus.Status = "degraded"
	} else {
		c.healthStatus.Status = "healthy"
	}

	return c.healthStatus
}

// Close cleans up resources
func (c *JobSpyAPIClient) Close() error {
	c.logger.Info("JobSpy API client shutting down")
	return nil
}