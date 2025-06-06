package worker

import (
	"context"
	"encoding/json"
	"fmt"
	"sync"
	"time"

	"github.com/sirupsen/logrus"
	"github.com/google/uuid"

	"github.com/jobspy/scrapers/internal/config"
	"github.com/jobspy/scrapers/internal/protocol"
	"github.com/jobspy/scrapers/internal/redis"
	"github.com/jobspy/scrapers/internal/scraper"
)

// Orchestrator manages multiple worker goroutines for job scraping
type Orchestrator struct {
	config       *config.Config
	logger       *logrus.Logger
	redisClient  *redis.Client
	scraperFactory ScraperFactory
	workers      []*Worker
	healthMonitor *HealthMonitor
	
	// Control channels
	ctx          context.Context
	cancel       context.CancelFunc
	shutdownCh   chan struct{}
	wg           sync.WaitGroup
	
	// Metrics
	metrics      *OrchestratorMetrics
	metricsLock  sync.RWMutex
}

// OrchestratorMetrics holds orchestrator-level metrics
type OrchestratorMetrics struct {
	StartTime           time.Time
	TasksProcessed      int64
	TasksSuccessful     int64
	TasksFailed         int64
	TasksTimeout        int64
	ActiveWorkers       int
	TotalWorkers        int
	LastTaskProcessed   time.Time
	AverageTaskDuration time.Duration
	ErrorRate           float64
}

// ScraperFactory interface for creating scrapers
type ScraperFactory interface {
	CreateScraper(scraperType protocol.ScraperType, config scraper.ScraperConfig) (scraper.Scraper, error)
	GetSupportedTypes() []protocol.ScraperType
}

// NewOrchestrator creates a new worker orchestrator
func NewOrchestrator(cfg *config.Config, logger *logrus.Logger, redisClient *redis.Client, factory ScraperFactory) *Orchestrator {
	ctx, cancel := context.WithCancel(context.Background())
	
	orchestrator := &Orchestrator{
		config:         cfg,
		logger:         logger,
		redisClient:    redisClient,
		scraperFactory: factory,
		ctx:            ctx,
		cancel:         cancel,
		shutdownCh:     make(chan struct{}),
		metrics: &OrchestratorMetrics{
			StartTime:     time.Now(),
			TotalWorkers:  cfg.Concurrency,
		},
	}
	
	// Initialize health monitor
	orchestrator.healthMonitor = NewHealthMonitor(cfg, logger, redisClient)
	
	return orchestrator
}

// Start starts the orchestrator and all worker goroutines
func (o *Orchestrator) Start() error {
	o.logger.WithFields(logrus.Fields{
		"worker_id":     o.config.WorkerID,
		"scraper_type":  o.config.ScraperType,
		"concurrency":   o.config.Concurrency,
		"region":        o.config.Region,
	}).Info("Starting scraper orchestrator")

	// Validate configuration
	if err := o.validateConfig(); err != nil {
		return fmt.Errorf("configuration validation failed: %w", err)
	}

	// Start health monitor
	if err := o.healthMonitor.Start(o.ctx); err != nil {
		return fmt.Errorf("failed to start health monitor: %w", err)
	}

	// Start metrics collection
	o.startMetricsCollection()

	// Create and start workers
	o.workers = make([]*Worker, o.config.Concurrency)
	for i := 0; i < o.config.Concurrency; i++ {
		workerConfig := o.createWorkerConfig(i)
		
		worker, err := NewWorker(workerConfig, o.logger, o.redisClient, o.scraperFactory)
		if err != nil {
			return fmt.Errorf("failed to create worker %d: %w", i, err)
		}
		
		o.workers[i] = worker
		
		// Start worker in goroutine
		o.wg.Add(1)
		go o.runWorker(worker, i)
	}

	o.updateMetrics(func(m *OrchestratorMetrics) {
		m.ActiveWorkers = o.config.Concurrency
	})

	o.logger.WithField("active_workers", o.config.Concurrency).Info("All workers started successfully")
	return nil
}

// Stop gracefully stops the orchestrator and all workers
func (o *Orchestrator) Stop() error {
	o.logger.Info("Stopping scraper orchestrator...")
	
	// Signal shutdown
	close(o.shutdownCh)
	o.cancel()
	
	// Wait for all workers to complete with timeout
	done := make(chan struct{})
	go func() {
		o.wg.Wait()
		close(done)
	}()
	
	select {
	case <-done:
		o.logger.Info("All workers stopped gracefully")
	case <-time.After(30 * time.Second):
		o.logger.Warn("Timeout waiting for workers to stop, forcing shutdown")
	}
	
	// Stop health monitor
	if err := o.healthMonitor.Stop(); err != nil {
		o.logger.WithError(err).Error("Error stopping health monitor")
	}
	
	// Close Redis client
	if err := o.redisClient.Close(); err != nil {
		o.logger.WithError(err).Error("Error closing Redis client")
	}
	
	o.updateMetrics(func(m *OrchestratorMetrics) {
		m.ActiveWorkers = 0
	})
	
	o.logger.Info("Scraper orchestrator stopped")
	return nil
}

// GetMetrics returns current orchestrator metrics
func (o *Orchestrator) GetMetrics() *OrchestratorMetrics {
	o.metricsLock.RLock()
	defer o.metricsLock.RUnlock()
	
	// Create a copy to avoid race conditions
	metrics := *o.metrics
	return &metrics
}

// GetHealthStatus returns current health status
func (o *Orchestrator) GetHealthStatus() *protocol.HealthStatus {
	metrics := o.GetMetrics()
	
	status := "healthy"
	if metrics.ActiveWorkers == 0 {
		status = "unhealthy"
	} else if metrics.ErrorRate > 0.5 {
		status = "degraded"
	}
	
	return &protocol.HealthStatus{
		WorkerID:                 o.config.WorkerID,
		ScraperType:              protocol.ScraperType(o.config.ScraperType),
		Status:                   status,
		ActiveTasks:              int(metrics.TasksProcessed - metrics.TasksSuccessful - metrics.TasksFailed),
		CompletedTasksLastHour:   int(metrics.TasksSuccessful),
		ErrorRateLastHour:        metrics.ErrorRate,
		MemoryUsageMB:            0, // TODO: Implement memory monitoring
		CPUUsagePercent:          0, // TODO: Implement CPU monitoring
		ProxyPoolSize:            len(o.config.ProxyPool),
		ProxySuccessRate:         100.0, // TODO: Implement proxy monitoring
		LastSuccessfulScrape:     metrics.LastTaskProcessed.Format(time.RFC3339),
		Timestamp:                time.Now().UTC().Format(time.RFC3339),
	}
}

// runWorker runs a single worker until shutdown
func (o *Orchestrator) runWorker(worker *Worker, workerIndex int) {
	defer o.wg.Done()
	
	workerLogger := o.logger.WithField("worker_index", workerIndex)
	workerLogger.Info("Starting worker")
	
	for {
		select {
		case <-o.shutdownCh:
			workerLogger.Info("Worker received shutdown signal")
			return
		case <-o.ctx.Done():
			workerLogger.Info("Worker context cancelled")
			return
		default:
		}
		
		// Process next task
		if err := o.processNextTask(worker, workerLogger); err != nil {
			if err == context.DeadlineExceeded || err == context.Canceled {
				workerLogger.Debug("Worker task cancelled")
				continue
			}
			
			workerLogger.WithError(err).Error("Error processing task")
			
			// Add delay before retrying on error
			select {
			case <-time.After(5 * time.Second):
			case <-o.shutdownCh:
				return
			}
		}
	}
}

// processNextTask processes the next available task
func (o *Orchestrator) processNextTask(worker *Worker, logger *logrus.Entry) error {
	// Get task queue for this scraper type
	queueName := protocol.GetTaskQueue(protocol.ScraperType(o.config.ScraperType))
	
	// Pop task with timeout
	var task protocol.ScrapingTask
	taskAvailable, err := o.redisClient.PopTask(queueName, time.Duration(o.config.QueueTimeout)*time.Second, &task)
	if err != nil {
		return fmt.Errorf("failed to pop task from queue: %w", err)
	}
	
	if !taskAvailable {
		// No task available, continue polling
		return nil
	}
	
	// Update metrics
	o.updateMetrics(func(m *OrchestratorMetrics) {
		m.TasksProcessed++
		m.LastTaskProcessed = time.Now()
	})
	
	logger = logger.WithFields(logrus.Fields{
		"task_id":      task.TaskID,
		"scraper_type": task.ScraperType,
		"search_term":  task.Params.SearchTerm,
		"location":     task.Params.Location,
	})
	
	logger.Info("Processing scraping task")
	
	// Create context with timeout
	taskCtx, cancel := context.WithTimeout(o.ctx, time.Duration(task.Timeout)*time.Second)
	defer cancel()
	
	// Process task
	startTime := time.Now()
	result, err := worker.ProcessTask(taskCtx, &task)
	duration := time.Since(startTime)
	
	if err != nil {
		logger.WithError(err).WithField("duration", duration).Error("Task processing failed")
		
		// Update failure metrics
		o.updateMetrics(func(m *OrchestratorMetrics) {
			m.TasksFailed++
			m.ErrorRate = float64(m.TasksFailed) / float64(m.TasksProcessed)
		})
		
		// Send error result
		result = &protocol.ScrapingResult{
			TaskID:        task.TaskID,
			Status:        protocol.TaskStatusFailed,
			ScraperType:   task.ScraperType,
			ExecutionTime: duration.Seconds(),
			CompletedAt:   time.Now().UTC().Format(time.RFC3339),
			Error:         &err.Error(),
		}
	} else {
		logger.WithFields(logrus.Fields{
			"duration":   duration,
			"jobs_found": result.JobsFound,
		}).Info("Task completed successfully")
		
		// Update success metrics
		o.updateMetrics(func(m *OrchestratorMetrics) {
			m.TasksSuccessful++
			m.AverageTaskDuration = time.Duration((int64(m.AverageTaskDuration)*m.TasksSuccessful + int64(duration)) / (m.TasksSuccessful + 1))
			m.ErrorRate = float64(m.TasksFailed) / float64(m.TasksProcessed)
		})
	}
	
	// Ensure task ID is set
	result.TaskID = task.TaskID
	
	// Publish result
	resultsQueue := protocol.ChannelScrapingResults
	if err := o.redisClient.PublishResult(resultsQueue, result); err != nil {
		logger.WithError(err).Error("Failed to publish task result")
		return fmt.Errorf("failed to publish result: %w", err)
	}
	
	logger.Debug("Task result published successfully")
	return nil
}

// createWorkerConfig creates configuration for a worker
func (o *Orchestrator) createWorkerConfig(index int) *WorkerConfig {
	return &WorkerConfig{
		WorkerID:       fmt.Sprintf("%s-worker-%d", o.config.WorkerID, index),
		ScraperType:    o.config.ScraperType,
		MaxRetries:     o.config.MaxRetries,
		RetryDelay:     time.Duration(o.config.RetryDelay) * time.Second,
		TaskTimeout:    time.Duration(o.config.TaskTimeout) * time.Second,
		MetricsEnabled: o.config.MetricsEnabled,
	}
}

// validateConfig validates the orchestrator configuration
func (o *Orchestrator) validateConfig() error {
	if o.config.ScraperType == "" {
		return fmt.Errorf("scraper_type is required")
	}
	
	if !protocol.IsValidScraperType(o.config.ScraperType) {
		return fmt.Errorf("invalid scraper_type: %s", o.config.ScraperType)
	}
	
	if o.config.Concurrency <= 0 || o.config.Concurrency > 100 {
		return fmt.Errorf("concurrency must be between 1 and 100")
	}
	
	return nil
}

// startMetricsCollection starts background metrics collection
func (o *Orchestrator) startMetricsCollection() {
	if !o.config.MetricsEnabled {
		return
	}
	
	o.wg.Add(1)
	go func() {
		defer o.wg.Done()
		
		ticker := time.NewTicker(o.config.MetricsInterval)
		defer ticker.Stop()
		
		for {
			select {
			case <-ticker.C:
				o.reportMetrics()
			case <-o.shutdownCh:
				return
			case <-o.ctx.Done():
				return
			}
		}
	}()
}

// reportMetrics reports current metrics to monitoring systems
func (o *Orchestrator) reportMetrics() {
	metrics := o.GetMetrics()
	healthStatus := o.GetHealthStatus()
	
	// Report to health monitor
	o.healthMonitor.UpdateHealth(healthStatus)
	
	// Log metrics
	o.logger.WithFields(logrus.Fields{
		"tasks_processed":   metrics.TasksProcessed,
		"tasks_successful":  metrics.TasksSuccessful,
		"tasks_failed":      metrics.TasksFailed,
		"error_rate":        metrics.ErrorRate,
		"active_workers":    metrics.ActiveWorkers,
		"avg_task_duration": metrics.AverageTaskDuration,
	}).Info("Orchestrator metrics")
}

// updateMetrics safely updates orchestrator metrics
func (o *Orchestrator) updateMetrics(updateFunc func(*OrchestratorMetrics)) {
	o.metricsLock.Lock()
	defer o.metricsLock.Unlock()
	updateFunc(o.metrics)
}