package worker

import (
	"context"
	"fmt"
	"time"

	"github.com/sirupsen/logrus"
	"github.com/google/uuid"

	"github.com/jobspy/scrapers/internal/protocol"
	"github.com/jobspy/scrapers/internal/redis"
	"github.com/jobspy/scrapers/internal/scraper"
)

// Worker represents a single scraping worker
type Worker struct {
	config         *WorkerConfig
	logger         *logrus.Entry
	redisClient    *redis.Client
	scraperFactory ScraperFactory
	scraper        scraper.Scraper
	metrics        *WorkerMetrics
}

// WorkerConfig holds configuration for a worker
type WorkerConfig struct {
	WorkerID       string
	ScraperType    string
	MaxRetries     int
	RetryDelay     time.Duration
	TaskTimeout    time.Duration
	MetricsEnabled bool
}

// WorkerMetrics holds worker-level metrics
type WorkerMetrics struct {
	TasksProcessed   int64
	TasksSuccessful  int64
	TasksFailed      int64
	TasksRetried     int64
	LastTaskTime     time.Time
	TotalProcessTime time.Duration
	AverageTaskTime  time.Duration
}

// NewWorker creates a new worker instance
func NewWorker(config *WorkerConfig, logger *logrus.Logger, redisClient *redis.Client, factory ScraperFactory) (*Worker, error) {
	workerLogger := logger.WithFields(logrus.Fields{
		"worker_id":    config.WorkerID,
		"scraper_type": config.ScraperType,
	})

	// Create scraper instance
	scraperConfig := scraper.ScraperConfig{
		WorkerID:      config.WorkerID,
		Timeout:       config.TaskTimeout,
		// TODO: Add more scraper-specific configuration
	}

	scraperInstance, err := factory.CreateScraper(protocol.ScraperType(config.ScraperType), scraperConfig)
	if err != nil {
		return nil, fmt.Errorf("failed to create scraper: %w", err)
	}

	return &Worker{
		config:         config,
		logger:         workerLogger,
		redisClient:    redisClient,
		scraperFactory: factory,
		scraper:        scraperInstance,
		metrics:        &WorkerMetrics{},
	}, nil
}

// ProcessTask processes a single scraping task with retry logic
func (w *Worker) ProcessTask(ctx context.Context, task *protocol.ScrapingTask) (*protocol.ScrapingResult, error) {
	startTime := time.Now()
	
	w.logger.WithFields(logrus.Fields{
		"task_id":      task.TaskID,
		"search_term":  task.Params.SearchTerm,
		"location":     task.Params.Location,
		"results_wanted": task.Params.ResultsWanted,
	}).Info("Starting task processing")

	// Validate task
	if err := task.Validate(); err != nil {
		w.updateMetrics(false, time.Since(startTime))
		return nil, fmt.Errorf("task validation failed: %w", err)
	}

	// Validate scraper params
	if err := w.scraper.ValidateParams(task.Params); err != nil {
		w.updateMetrics(false, time.Since(startTime))
		return nil, fmt.Errorf("scraper params validation failed: %w", err)
	}

	var result *protocol.ScrapingResult
	var lastErr error

	// Retry logic with exponential backoff
	for attempt := 0; attempt <= task.MaxRetries; attempt++ {
		if attempt > 0 {
			w.metrics.TasksRetried++
			
			// Calculate backoff delay
			backoffDelay := w.calculateBackoffDelay(attempt)
			w.logger.WithFields(logrus.Fields{
				"attempt": attempt,
				"delay":   backoffDelay,
			}).Info("Retrying task after delay")
			
			select {
			case <-time.After(backoffDelay):
			case <-ctx.Done():
				w.updateMetrics(false, time.Since(startTime))
				return nil, ctx.Err()
			}
		}

		// Create context with timeout for this attempt
		attemptCtx, cancel := context.WithTimeout(ctx, w.config.TaskTimeout)
		
		// Execute scraping
		attemptStart := time.Now()
		result, lastErr = w.scraper.ScrapeJobs(attemptCtx, task.Params)
		attemptDuration := time.Since(attemptStart)
		
		cancel()

		if lastErr == nil {
			// Success
			w.logger.WithFields(logrus.Fields{
				"attempt":       attempt + 1,
				"duration":      attemptDuration,
				"jobs_found":    result.JobsFound,
			}).Info("Task completed successfully")
			
			w.updateMetrics(true, time.Since(startTime))
			return result, nil
		}

		// Check if error is retryable
		if !w.isRetryableError(lastErr) {
			w.logger.WithError(lastErr).WithField("attempt", attempt+1).Error("Non-retryable error, stopping retries")
			break
		}

		w.logger.WithError(lastErr).WithFields(logrus.Fields{
			"attempt":  attempt + 1,
			"duration": attemptDuration,
		}).Warn("Task attempt failed, will retry")
	}

	// All attempts failed
	w.updateMetrics(false, time.Since(startTime))
	return nil, fmt.Errorf("task failed after %d attempts: %w", task.MaxRetries+1, lastErr)
}

// GetMetrics returns current worker metrics
func (w *Worker) GetMetrics() *WorkerMetrics {
	return w.metrics
}

// GetHealthStatus returns worker health status
func (w *Worker) GetHealthStatus() *protocol.HealthStatus {
	scraperHealth := w.scraper.GetHealthStatus()
	
	// Update with worker-specific metrics
	scraperHealth.WorkerID = w.config.WorkerID
	scraperHealth.ActiveTasks = 0 // TODO: Track active tasks
	scraperHealth.CompletedTasksLastHour = int(w.metrics.TasksSuccessful)
	
	if w.metrics.TasksProcessed > 0 {
		scraperHealth.ErrorRateLastHour = float64(w.metrics.TasksFailed) / float64(w.metrics.TasksProcessed)
	}
	
	return scraperHealth
}

// Close cleans up worker resources
func (w *Worker) Close() error {
	w.logger.Info("Shutting down worker")
	
	if err := w.scraper.Close(); err != nil {
		w.logger.WithError(err).Error("Error closing scraper")
		return err
	}
	
	return nil
}

// updateMetrics updates worker metrics
func (w *Worker) updateMetrics(success bool, duration time.Duration) {
	w.metrics.TasksProcessed++
	w.metrics.LastTaskTime = time.Now()
	w.metrics.TotalProcessTime += duration
	
	if w.metrics.TasksProcessed > 0 {
		w.metrics.AverageTaskTime = time.Duration(int64(w.metrics.TotalProcessTime) / w.metrics.TasksProcessed)
	}
	
	if success {
		w.metrics.TasksSuccessful++
	} else {
		w.metrics.TasksFailed++
	}
}

// calculateBackoffDelay calculates exponential backoff delay
func (w *Worker) calculateBackoffDelay(attempt int) time.Duration {
	baseDelay := w.config.RetryDelay
	if baseDelay == 0 {
		baseDelay = 5 * time.Second
	}
	
	// Exponential backoff: baseDelay * 2^(attempt-1)
	multiplier := 1 << uint(attempt-1) // 2^(attempt-1)
	if multiplier > 16 {
		multiplier = 16 // Cap at 16x base delay
	}
	
	delay := time.Duration(multiplier) * baseDelay
	
	// Add jitter (±25%)
	jitter := time.Duration(float64(delay) * 0.25 * (2*randFloat() - 1))
	return delay + jitter
}

// isRetryableError determines if an error should trigger a retry
func (w *Worker) isRetryableError(err error) bool {
	if err == nil {
		return false
	}
	
	// Check for specific error types
	if scrapingErr, ok := err.(scraper.ScrapingError); ok {
		return scrapingErr.Retryable
	}
	
	// Context errors are not retryable
	if err == context.DeadlineExceeded || err == context.Canceled {
		return false
	}
	
	// Validation errors are not retryable
	if _, ok := err.(scraper.ValidationError); ok {
		return false
	}
	
	// Default: retry network and temporary errors
	errStr := err.Error()
	retryablePatterns := []string{
		"connection refused",
		"timeout",
		"temporary failure",
		"service unavailable",
		"internal server error",
		"bad gateway",
		"gateway timeout",
	}
	
	for _, pattern := range retryablePatterns {
		if contains(errStr, pattern) {
			return true
		}
	}
	
	return false
}

// Helper functions
func randFloat() float64 {
	// Simple pseudo-random float [0,1)
	// In production, use crypto/rand for better randomness
	return float64(time.Now().UnixNano()%1000) / 1000.0
}

func contains(haystack, needle string) bool {
	return len(haystack) >= len(needle) && 
		   (haystack == needle || 
		    (len(haystack) > len(needle) && 
		     (haystack[:len(needle)] == needle || 
		      haystack[len(haystack)-len(needle):] == needle ||
		      indexOf(haystack, needle) >= 0)))
}

func indexOf(haystack, needle string) int {
	for i := 0; i <= len(haystack)-len(needle); i++ {
		if haystack[i:i+len(needle)] == needle {
			return i
		}
	}
	return -1
}