package worker

import (
	"context"
	"runtime"
	"sync"
	"time"

	"github.com/sirupsen/logrus"

	"github.com/jobspy/scrapers/internal/config"
	"github.com/jobspy/scrapers/internal/protocol"
	"github.com/jobspy/scrapers/internal/redis"
)

// HealthMonitor monitors and reports worker health status
type HealthMonitor struct {
	config      *config.Config
	logger      *logrus.Logger
	redisClient *redis.Client
	
	// Health data
	healthStatus *protocol.HealthStatus
	healthLock   sync.RWMutex
	
	// Control
	ctx        context.Context
	cancel     context.CancelFunc
	shutdownCh chan struct{}
	wg         sync.WaitGroup
	
	// Metrics
	taskMetrics      *TaskMetrics
	systemMetrics    *SystemMetrics
	metricsLock      sync.RWMutex
}

// TaskMetrics holds task-related metrics
type TaskMetrics struct {
	TasksCompletedLastHour   int
	TasksFailedLastHour      int
	LastSuccessfulScrape     time.Time
	ErrorRateLastHour        float64
	AverageResponseTime      time.Duration
	
	// Rolling windows
	successWindow    []time.Time
	errorWindow      []time.Time
	responseTimeWindow []time.Duration
}

// SystemMetrics holds system-related metrics
type SystemMetrics struct {
	MemoryUsageMB   float64
	CPUUsagePercent float64
	GoroutineCount  int
	LastUpdated     time.Time
}

// NewHealthMonitor creates a new health monitor
func NewHealthMonitor(config *config.Config, logger *logrus.Logger, redisClient *redis.Client) *HealthMonitor {
	ctx, cancel := context.WithCancel(context.Background())
	
	return &HealthMonitor{
		config:      config,
		logger:      logger,
		redisClient: redisClient,
		ctx:         ctx,
		cancel:      cancel,
		shutdownCh:  make(chan struct{}),
		healthStatus: protocol.NewHealthStatus(config.WorkerID, protocol.ScraperType(config.ScraperType)),
		taskMetrics: &TaskMetrics{
			successWindow:      make([]time.Time, 0),
			errorWindow:        make([]time.Time, 0),
			responseTimeWindow: make([]time.Duration, 0),
		},
		systemMetrics: &SystemMetrics{},
	}
}

// Start starts the health monitoring
func (hm *HealthMonitor) Start(ctx context.Context) error {
	hm.logger.Info("Starting health monitor")
	
	// Start health reporting goroutine
	hm.wg.Add(1)
	go hm.healthReportingLoop()
	
	// Start system metrics collection
	hm.wg.Add(1)
	go hm.systemMetricsLoop()
	
	return nil
}

// Stop stops the health monitoring
func (hm *HealthMonitor) Stop() error {
	hm.logger.Info("Stopping health monitor")
	
	close(hm.shutdownCh)
	hm.cancel()
	
	// Wait for goroutines to finish
	done := make(chan struct{})
	go func() {
		hm.wg.Wait()
		close(done)
	}()
	
	select {
	case <-done:
		hm.logger.Info("Health monitor stopped gracefully")
	case <-time.After(10 * time.Second):
		hm.logger.Warn("Health monitor stop timeout")
	}
	
	return nil
}

// UpdateHealth updates the health status
func (hm *HealthMonitor) UpdateHealth(status *protocol.HealthStatus) {
	hm.healthLock.Lock()
	defer hm.healthLock.Unlock()
	
	hm.healthStatus = status
	hm.healthStatus.Timestamp = time.Now().UTC().Format(time.RFC3339)
}

// GetHealth returns current health status
func (hm *HealthMonitor) GetHealth() *protocol.HealthStatus {
	hm.healthLock.RLock()
	defer hm.healthLock.RUnlock()
	
	// Create a copy
	health := *hm.healthStatus
	return &health
}

// ReportTaskSuccess reports a successful task completion
func (hm *HealthMonitor) ReportTaskSuccess(jobsFound int, duration time.Duration) {
	hm.metricsLock.Lock()
	defer hm.metricsLock.Unlock()
	
	now := time.Now()
	
	// Add to success window
	hm.taskMetrics.successWindow = append(hm.taskMetrics.successWindow, now)
	hm.taskMetrics.responseTimeWindow = append(hm.taskMetrics.responseTimeWindow, duration)
	hm.taskMetrics.LastSuccessfulScrape = now
	
	// Clean old entries (older than 1 hour)
	hm.cleanOldEntries()
	
	// Update metrics
	hm.updateTaskMetrics()
	
	hm.logger.WithFields(logrus.Fields{
		"jobs_found": jobsFound,
		"duration":   duration,
	}).Debug("Task success reported")
}

// ReportTaskError reports a task error
func (hm *HealthMonitor) ReportTaskError(error string, metadata map[string]interface{}) {
	hm.metricsLock.Lock()
	defer hm.metricsLock.Unlock()
	
	now := time.Now()
	
	// Add to error window
	hm.taskMetrics.errorWindow = append(hm.taskMetrics.errorWindow, now)
	
	// Clean old entries
	hm.cleanOldEntries()
	
	// Update metrics
	hm.updateTaskMetrics()
	
	hm.logger.WithFields(logrus.Fields{
		"error":    error,
		"metadata": metadata,
	}).Debug("Task error reported")
	
	// Report error to Redis
	go hm.reportErrorToRedis(error, metadata)
}

// IsHealthy returns whether the worker is healthy
func (hm *HealthMonitor) IsHealthy() bool {
	health := hm.GetHealth()
	return health.Status == "healthy"
}

// healthReportingLoop periodically reports health status to Redis
func (hm *HealthMonitor) healthReportingLoop() {
	defer hm.wg.Done()
	
	ticker := time.NewTicker(hm.config.HealthCheckInterval)
	defer ticker.Stop()
	
	for {
		select {
		case <-ticker.C:
			hm.reportHealthStatus()
		case <-hm.shutdownCh:
			return
		case <-hm.ctx.Done():
			return
		}
	}
}

// systemMetricsLoop periodically collects system metrics
func (hm *HealthMonitor) systemMetricsLoop() {
	defer hm.wg.Done()
	
	ticker := time.NewTicker(30 * time.Second) // Collect system metrics every 30 seconds
	defer ticker.Stop()
	
	for {
		select {
		case <-ticker.C:
			hm.collectSystemMetrics()
		case <-hm.shutdownCh:
			return
		case <-hm.ctx.Done():
			return
		}
	}
}

// reportHealthStatus reports current health status to Redis
func (hm *HealthMonitor) reportHealthStatus() {
	// Update health with current metrics
	hm.updateHealthFromMetrics()
	
	health := hm.GetHealth()
	healthKey := protocol.GetHealthKey(protocol.ScraperType(hm.config.ScraperType), hm.config.WorkerID)
	
	// Set health with TTL (2x health check interval)
	ttl := hm.config.HealthCheckInterval * 2
	if err := hm.redisClient.SetHealth(healthKey, health, ttl); err != nil {
		hm.logger.WithError(err).Error("Failed to report health status to Redis")
		return
	}
	
	hm.logger.WithFields(logrus.Fields{
		"status":                health.Status,
		"active_tasks":          health.ActiveTasks,
		"completed_tasks":       health.CompletedTasksLastHour,
		"error_rate":            health.ErrorRateLastHour,
		"memory_usage_mb":       health.MemoryUsageMB,
	}).Debug("Health status reported")
}

// collectSystemMetrics collects system performance metrics
func (hm *HealthMonitor) collectSystemMetrics() {
	hm.metricsLock.Lock()
	defer hm.metricsLock.Unlock()
	
	var memStats runtime.MemStats
	runtime.ReadMemStats(&memStats)
	
	hm.systemMetrics.MemoryUsageMB = float64(memStats.Alloc) / 1024 / 1024
	hm.systemMetrics.GoroutineCount = runtime.NumGoroutine()
	hm.systemMetrics.LastUpdated = time.Now()
	
	// TODO: Implement CPU usage collection
	// This requires platform-specific code or external libraries
	hm.systemMetrics.CPUUsagePercent = 0.0
}

// updateHealthFromMetrics updates health status from current metrics
func (hm *HealthMonitor) updateHealthFromMetrics() {
	hm.metricsLock.RLock()
	taskMetrics := *hm.taskMetrics
	systemMetrics := *hm.systemMetrics
	hm.metricsLock.RUnlock()
	
	hm.healthLock.Lock()
	defer hm.healthLock.Unlock()
	
	// Update health status fields
	hm.healthStatus.CompletedTasksLastHour = taskMetrics.TasksCompletedLastHour
	hm.healthStatus.ErrorRateLastHour = taskMetrics.ErrorRateLastHour
	hm.healthStatus.MemoryUsageMB = systemMetrics.MemoryUsageMB
	hm.healthStatus.CPUUsagePercent = systemMetrics.CPUUsagePercent
	
	if !taskMetrics.LastSuccessfulScrape.IsZero() {
		hm.healthStatus.LastSuccessfulScrape = taskMetrics.LastSuccessfulScrape.Format(time.RFC3339)
	}
	
	// Determine overall health status
	hm.healthStatus.Status = hm.calculateHealthStatus(taskMetrics, systemMetrics)
	hm.healthStatus.Timestamp = time.Now().UTC().Format(time.RFC3339)
}

// calculateHealthStatus determines overall health based on metrics
func (hm *HealthMonitor) calculateHealthStatus(taskMetrics TaskMetrics, systemMetrics SystemMetrics) string {
	// Check if worker has been inactive for too long
	if !taskMetrics.LastSuccessfulScrape.IsZero() &&
		time.Since(taskMetrics.LastSuccessfulScrape) > 30*time.Minute {
		return "unhealthy"
	}
	
	// Check error rate
	if taskMetrics.ErrorRateLastHour > 0.8 {
		return "unhealthy"
	} else if taskMetrics.ErrorRateLastHour > 0.5 {
		return "degraded"
	}
	
	// Check memory usage
	if systemMetrics.MemoryUsageMB > 1024 { // > 1GB
		return "degraded"
	}
	
	// Check CPU usage
	if systemMetrics.CPUUsagePercent > 90 {
		return "degraded"
	}
	
	return "healthy"
}

// cleanOldEntries removes entries older than 1 hour from time windows
func (hm *HealthMonitor) cleanOldEntries() {
	cutoff := time.Now().Add(-time.Hour)
	
	// Clean success window
	for i, t := range hm.taskMetrics.successWindow {
		if t.After(cutoff) {
			hm.taskMetrics.successWindow = hm.taskMetrics.successWindow[i:]
			break
		}
		if i == len(hm.taskMetrics.successWindow)-1 {
			hm.taskMetrics.successWindow = hm.taskMetrics.successWindow[:0]
		}
	}
	
	// Clean error window
	for i, t := range hm.taskMetrics.errorWindow {
		if t.After(cutoff) {
			hm.taskMetrics.errorWindow = hm.taskMetrics.errorWindow[i:]
			break
		}
		if i == len(hm.taskMetrics.errorWindow)-1 {
			hm.taskMetrics.errorWindow = hm.taskMetrics.errorWindow[:0]
		}
	}
	
	// Clean response time window
	if len(hm.taskMetrics.responseTimeWindow) > len(hm.taskMetrics.successWindow) {
		hm.taskMetrics.responseTimeWindow = hm.taskMetrics.responseTimeWindow[len(hm.taskMetrics.responseTimeWindow)-len(hm.taskMetrics.successWindow):]
	}
}

// updateTaskMetrics recalculates task metrics from current windows
func (hm *HealthMonitor) updateTaskMetrics() {
	successCount := len(hm.taskMetrics.successWindow)
	errorCount := len(hm.taskMetrics.errorWindow)
	totalTasks := successCount + errorCount
	
	hm.taskMetrics.TasksCompletedLastHour = successCount
	hm.taskMetrics.TasksFailedLastHour = errorCount
	
	if totalTasks > 0 {
		hm.taskMetrics.ErrorRateLastHour = float64(errorCount) / float64(totalTasks)
	} else {
		hm.taskMetrics.ErrorRateLastHour = 0.0
	}
	
	// Calculate average response time
	if len(hm.taskMetrics.responseTimeWindow) > 0 {
		var total time.Duration
		for _, duration := range hm.taskMetrics.responseTimeWindow {
			total += duration
		}
		hm.taskMetrics.AverageResponseTime = total / time.Duration(len(hm.taskMetrics.responseTimeWindow))
	}
}

// reportErrorToRedis reports an error to the Redis error channel
func (hm *HealthMonitor) reportErrorToRedis(error string, metadata map[string]interface{}) {
	errorReport := protocol.ErrorReport{
		TaskID:      "", // Will be set by caller if available
		ScraperType: protocol.ScraperType(hm.config.ScraperType),
		Error:       error,
		Metadata:    metadata,
		Timestamp:   time.Now().UTC().Format(time.RFC3339),
	}
	
	if err := hm.redisClient.PublishResult(protocol.ChannelErrorReporting, errorReport); err != nil {
		hm.logger.WithError(err).Error("Failed to report error to Redis")
	}
}