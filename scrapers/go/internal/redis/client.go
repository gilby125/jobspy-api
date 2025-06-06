package redis

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/go-redis/redis/v8"
	"github.com/sirupsen/logrus"
)

// Client wraps Redis client with production-ready features
type Client struct {
	client *redis.Client
	ctx    context.Context
	logger *logrus.Logger
	config *Config
}

// Config holds Redis client configuration
type Config struct {
	URL              string
	Password         string
	DB               int
	PoolSize         int
	MinIdleConns     int
	MaxConnAge       time.Duration
	PoolTimeout      time.Duration
	IdleTimeout      time.Duration
	IdleCheckFreq    time.Duration
	ReadTimeout      time.Duration
	WriteTimeout     time.Duration
	DialTimeout      time.Duration
	MaxRetries       int
	MinRetryBackoff  time.Duration
	MaxRetryBackoff  time.Duration
}

// DefaultConfig returns Redis config with production-ready defaults
func DefaultConfig() *Config {
	return &Config{
		URL:              "redis://localhost:6379",
		DB:               0,
		PoolSize:         100,
		MinIdleConns:     10,
		MaxConnAge:       30 * time.Minute,
		PoolTimeout:      5 * time.Second,
		IdleTimeout:      5 * time.Minute,
		IdleCheckFreq:    1 * time.Minute,
		ReadTimeout:      30 * time.Second,
		WriteTimeout:     30 * time.Second,
		DialTimeout:      10 * time.Second,
		MaxRetries:       3,
		MinRetryBackoff:  500 * time.Millisecond,
		MaxRetryBackoff:  2 * time.Second,
	}
}

// NewClient creates a new production-ready Redis client
func NewClient(config *Config, logger *logrus.Logger) (*Client, error) {
	if config == nil {
		config = DefaultConfig()
	}

	// Parse Redis URL
	opts, err := redis.ParseURL(config.URL)
	if err != nil {
		return nil, fmt.Errorf("failed to parse Redis URL: %w", err)
	}

	// Apply custom configuration
	opts.Password = config.Password
	opts.DB = config.DB
	opts.PoolSize = config.PoolSize
	opts.MinIdleConns = config.MinIdleConns
	opts.MaxConnAge = config.MaxConnAge
	opts.PoolTimeout = config.PoolTimeout
	opts.IdleTimeout = config.IdleTimeout
	opts.IdleCheckFreq = config.IdleCheckFreq
	opts.ReadTimeout = config.ReadTimeout
	opts.WriteTimeout = config.WriteTimeout
	opts.DialTimeout = config.DialTimeout
	opts.MaxRetries = config.MaxRetries
	opts.MinRetryBackoff = config.MinRetryBackoff
	opts.MaxRetryBackoff = config.MaxRetryBackoff

	// Enable connection pooling and health checks
	opts.OnConnect = func(ctx context.Context, cn *redis.Conn) error {
		logger.Debug("New Redis connection established")
		return nil
	}

	client := redis.NewClient(opts)

	// Test connection
	ctx := context.Background()
	if err := client.Ping(ctx).Err(); err != nil {
		return nil, fmt.Errorf("failed to connect to Redis: %w", err)
	}

	logger.WithFields(logrus.Fields{
		"url":       config.URL,
		"db":        config.DB,
		"pool_size": config.PoolSize,
	}).Info("Redis client connected successfully")

	return &Client{
		client: client,
		ctx:    context.Background(),
		logger: logger,
		config: config,
	}, nil
}

// Close closes the Redis connection
func (c *Client) Close() error {
	return c.client.Close()
}

// Health checks Redis connection health
func (c *Client) Health() error {
	ctx, cancel := context.WithTimeout(c.ctx, 5*time.Second)
	defer cancel()

	if err := c.client.Ping(ctx).Err(); err != nil {
		return fmt.Errorf("Redis health check failed: %w", err)
	}

	return nil
}

// GetStats returns Redis connection pool statistics
func (c *Client) GetStats() *redis.PoolStats {
	return c.client.PoolStats()
}

// --- Queue Operations ---

// PushTask pushes a task to a queue (left push for FIFO)
func (c *Client) PushTask(queue string, task interface{}) error {
	data, err := json.Marshal(task)
	if err != nil {
		return fmt.Errorf("failed to marshal task: %w", err)
	}

	ctx, cancel := context.WithTimeout(c.ctx, c.config.WriteTimeout)
	defer cancel()

	if err := c.client.LPush(ctx, queue, data).Err(); err != nil {
		return fmt.Errorf("failed to push task to queue %s: %w", queue, err)
	}

	c.logger.WithFields(logrus.Fields{
		"queue": queue,
		"size":  len(data),
	}).Debug("Task pushed to queue")

	return nil
}

// PopTask pops a task from a queue with timeout (blocking right pop)
func (c *Client) PopTask(queue string, timeout time.Duration, result interface{}) (bool, error) {
	ctx, cancel := context.WithTimeout(c.ctx, timeout+5*time.Second)
	defer cancel()

	data, err := c.client.BRPop(ctx, timeout, queue).Result()
	if err != nil {
		if err == redis.Nil {
			// No data available within timeout
			return false, nil
		}
		return false, fmt.Errorf("failed to pop task from queue %s: %w", queue, err)
	}

	// BRPop returns [queue_name, data]
	if len(data) < 2 {
		return false, fmt.Errorf("invalid response from BRPop")
	}

	if err := json.Unmarshal([]byte(data[1]), result); err != nil {
		return false, fmt.Errorf("failed to unmarshal task: %w", err)
	}

	c.logger.WithFields(logrus.Fields{
		"queue": queue,
		"size":  len(data[1]),
	}).Debug("Task popped from queue")

	return true, nil
}

// GetQueueLength returns the number of items in a queue
func (c *Client) GetQueueLength(queue string) (int64, error) {
	ctx, cancel := context.WithTimeout(c.ctx, c.config.ReadTimeout)
	defer cancel()

	length, err := c.client.LLen(ctx, queue).Result()
	if err != nil {
		return 0, fmt.Errorf("failed to get queue length for %s: %w", queue, err)
	}

	return length, nil
}

// ClearQueue removes all items from a queue
func (c *Client) ClearQueue(queue string) error {
	ctx, cancel := context.WithTimeout(c.ctx, c.config.WriteTimeout)
	defer cancel()

	if err := c.client.Del(ctx, queue).Err(); err != nil {
		return fmt.Errorf("failed to clear queue %s: %w", queue, err)
	}

	c.logger.WithField("queue", queue).Info("Queue cleared")
	return nil
}

// --- Result Operations ---

// PublishResult publishes a result to a results queue
func (c *Client) PublishResult(queue string, result interface{}) error {
	data, err := json.Marshal(result)
	if err != nil {
		return fmt.Errorf("failed to marshal result: %w", err)
	}

	ctx, cancel := context.WithTimeout(c.ctx, c.config.WriteTimeout)
	defer cancel()

	if err := c.client.LPush(ctx, queue, data).Err(); err != nil {
		return fmt.Errorf("failed to publish result to queue %s: %w", queue, err)
	}

	c.logger.WithFields(logrus.Fields{
		"queue": queue,
		"size":  len(data),
	}).Debug("Result published to queue")

	return nil
}

// --- Health Monitoring ---

// SetHealth sets worker health status with TTL
func (c *Client) SetHealth(key string, health interface{}, ttl time.Duration) error {
	data, err := json.Marshal(health)
	if err != nil {
		return fmt.Errorf("failed to marshal health data: %w", err)
	}

	ctx, cancel := context.WithTimeout(c.ctx, c.config.WriteTimeout)
	defer cancel()

	if err := c.client.Set(ctx, key, data, ttl).Err(); err != nil {
		return fmt.Errorf("failed to set health status: %w", err)
	}

	return nil
}

// GetHealth gets worker health status
func (c *Client) GetHealth(key string, result interface{}) (bool, error) {
	ctx, cancel := context.WithTimeout(c.ctx, c.config.ReadTimeout)
	defer cancel()

	data, err := c.client.Get(ctx, key).Result()
	if err != nil {
		if err == redis.Nil {
			return false, nil // Key doesn't exist
		}
		return false, fmt.Errorf("failed to get health status: %w", err)
	}

	if err := json.Unmarshal([]byte(data), result); err != nil {
		return false, fmt.Errorf("failed to unmarshal health data: %w", err)
	}

	return true, nil
}

// GetAllHealthKeys gets all health monitoring keys matching a pattern
func (c *Client) GetAllHealthKeys(pattern string) ([]string, error) {
	ctx, cancel := context.WithTimeout(c.ctx, c.config.ReadTimeout)
	defer cancel()

	keys, err := c.client.Keys(ctx, pattern).Result()
	if err != nil {
		return nil, fmt.Errorf("failed to get health keys: %w", err)
	}

	return keys, nil
}

// --- Pub/Sub Operations ---

// Subscribe subscribes to a Redis channel
func (c *Client) Subscribe(channels ...string) *redis.PubSub {
	return c.client.Subscribe(c.ctx, channels...)
}

// Publish publishes a message to a Redis channel
func (c *Client) Publish(channel string, message interface{}) error {
	data, err := json.Marshal(message)
	if err != nil {
		return fmt.Errorf("failed to marshal message: %w", err)
	}

	ctx, cancel := context.WithTimeout(c.ctx, c.config.WriteTimeout)
	defer cancel()

	if err := c.client.Publish(ctx, channel, data).Err(); err != nil {
		return fmt.Errorf("failed to publish to channel %s: %w", channel, err)
	}

	return nil
}

// --- Error Reporting ---

// ReportError reports an error to the error queue
func (c *Client) ReportError(queue string, taskID string, scraperType string, error string, metadata map[string]interface{}) error {
	errorReport := map[string]interface{}{
		"task_id":      taskID,
		"scraper_type": scraperType,
		"error":        error,
		"metadata":     metadata,
		"timestamp":    time.Now().UTC().Format(time.RFC3339),
	}

	return c.PublishResult(queue, errorReport)
}

// --- Utility Functions ---

// WithContext returns a new client with the given context
func (c *Client) WithContext(ctx context.Context) *Client {
	newClient := *c
	newClient.ctx = ctx
	return &newClient
}

// Pipeline creates a new Redis pipeline for batch operations
func (c *Client) Pipeline() redis.Pipeliner {
	return c.client.Pipeline()
}

// TxPipeline creates a new Redis transaction pipeline
func (c *Client) TxPipeline() redis.Pipeliner {
	return c.client.TxPipeline()
}