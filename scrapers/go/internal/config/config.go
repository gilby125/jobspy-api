package config

import (
	"fmt"
	"os"
	"strconv"
	"strings"
	"time"

	"github.com/spf13/viper"
)

// Config holds all configuration for the scraper workers
type Config struct {
	// Redis Configuration
	RedisURL      string        `mapstructure:"redis_url"`
	RedisPassword string        `mapstructure:"redis_password"`
	RedisDB       int           `mapstructure:"redis_db"`
	RedisTimeout  time.Duration `mapstructure:"redis_timeout"`

	// Worker Configuration
	WorkerID       string `mapstructure:"worker_id"`
	ScraperType    string `mapstructure:"scraper_type"`
	Region         string `mapstructure:"region"`
	Concurrency    int    `mapstructure:"concurrency"`
	QueueTimeout   int    `mapstructure:"queue_timeout"`
	TaskTimeout    int    `mapstructure:"task_timeout"`
	MaxRetries     int    `mapstructure:"max_retries"`
	RetryDelay     int    `mapstructure:"retry_delay"`

	// Anti-Detection Configuration
	ProxyPool           []string      `mapstructure:"proxy_pool"`
	UserAgents          []string      `mapstructure:"user_agents"`
	MinDelay            time.Duration `mapstructure:"min_delay"`
	MaxDelay            time.Duration `mapstructure:"max_delay"`
	BrowserMode         bool          `mapstructure:"browser_mode"`
	StealthMode         bool          `mapstructure:"stealth_mode"`
	RotateProxies       bool          `mapstructure:"rotate_proxies"`
	RotateUserAgents    bool          `mapstructure:"rotate_user_agents"`

	// Performance Configuration
	MaxIdleConns        int           `mapstructure:"max_idle_conns"`
	MaxConnsPerHost     int           `mapstructure:"max_conns_per_host"`
	IdleConnTimeout     time.Duration `mapstructure:"idle_conn_timeout"`
	TLSHandshakeTimeout time.Duration `mapstructure:"tls_handshake_timeout"`
	ResponseTimeout     time.Duration `mapstructure:"response_timeout"`

	// Monitoring Configuration
	MetricsEnabled       bool          `mapstructure:"metrics_enabled"`
	HealthCheckInterval  time.Duration `mapstructure:"health_check_interval"`
	MetricsInterval      time.Duration `mapstructure:"metrics_interval"`
	LogLevel             string        `mapstructure:"log_level"`

	// Site-Specific Configuration
	IndeedConfig    IndeedConfig    `mapstructure:"indeed"`
	LinkedInConfig  LinkedInConfig  `mapstructure:"linkedin"`
	GlassdoorConfig GlassdoorConfig `mapstructure:"glassdoor"`
}

// IndeedConfig holds Indeed-specific configuration
type IndeedConfig struct {
	BaseURL         string   `mapstructure:"base_url"`
	SearchPath      string   `mapstructure:"search_path"`
	MaxPages        int      `mapstructure:"max_pages"`
	ResultsPerPage  int      `mapstructure:"results_per_page"`
	AllowedDomains  []string `mapstructure:"allowed_domains"`
	RequestDelay    int      `mapstructure:"request_delay"`
	RateLimitRPM    int      `mapstructure:"rate_limit_rpm"`
}

// LinkedInConfig holds LinkedIn-specific configuration
type LinkedInConfig struct {
	BaseURL         string   `mapstructure:"base_url"`
	SearchPath      string   `mapstructure:"search_path"`
	MaxPages        int      `mapstructure:"max_pages"`
	ResultsPerPage  int      `mapstructure:"results_per_page"`
	AllowedDomains  []string `mapstructure:"allowed_domains"`
	RequestDelay    int      `mapstructure:"request_delay"`
	RateLimitRPM    int      `mapstructure:"rate_limit_rpm"`
	RequiresBrowser bool     `mapstructure:"requires_browser"`
}

// GlassdoorConfig holds Glassdoor-specific configuration
type GlassdoorConfig struct {
	BaseURL         string   `mapstructure:"base_url"`
	SearchPath      string   `mapstructure:"search_path"`
	MaxPages        int      `mapstructure:"max_pages"`
	ResultsPerPage  int      `mapstructure:"results_per_page"`
	AllowedDomains  []string `mapstructure:"allowed_domains"`
	RequestDelay    int      `mapstructure:"request_delay"`
	RateLimitRPM    int      `mapstructure:"rate_limit_rpm"`
}

// DefaultConfig returns a configuration with sensible defaults
func DefaultConfig() *Config {
	return &Config{
		// Redis defaults
		RedisURL:     "redis://localhost:6379",
		RedisDB:      0,
		RedisTimeout: 30 * time.Second,

		// Worker defaults
		WorkerID:     generateWorkerID(),
		Region:       "default",
		Concurrency:  10,
		QueueTimeout: 30,
		TaskTimeout:  300,
		MaxRetries:   3,
		RetryDelay:   60,

		// Anti-detection defaults
		MinDelay:         1 * time.Second,
		MaxDelay:         3 * time.Second,
		BrowserMode:      false,
		StealthMode:      true,
		RotateProxies:    true,
		RotateUserAgents: true,

		// Performance defaults
		MaxIdleConns:        100,
		MaxConnsPerHost:     10,
		IdleConnTimeout:     90 * time.Second,
		TLSHandshakeTimeout: 10 * time.Second,
		ResponseTimeout:     30 * time.Second,

		// Monitoring defaults
		MetricsEnabled:      true,
		HealthCheckInterval: 60 * time.Second,
		MetricsInterval:     300 * time.Second,
		LogLevel:            "info",

		// Default user agents
		UserAgents: []string{
			"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
			"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
			"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
			"Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
			"Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0",
		},

		// Site-specific defaults
		IndeedConfig: IndeedConfig{
			BaseURL:        "https://www.indeed.com",
			SearchPath:     "/jobs",
			MaxPages:       5,
			ResultsPerPage: 50,
			AllowedDomains: []string{"indeed.com"},
			RequestDelay:   2000,
			RateLimitRPM:   30,
		},

		LinkedInConfig: LinkedInConfig{
			BaseURL:         "https://www.linkedin.com",
			SearchPath:      "/jobs/search",
			MaxPages:        3,
			ResultsPerPage:  25,
			AllowedDomains:  []string{"linkedin.com"},
			RequestDelay:    3000,
			RateLimitRPM:    20,
			RequiresBrowser: true,
		},

		GlassdoorConfig: GlassdoorConfig{
			BaseURL:        "https://www.glassdoor.com",
			SearchPath:     "/Job/jobs.htm",
			MaxPages:       5,
			ResultsPerPage: 30,
			AllowedDomains: []string{"glassdoor.com"},
			RequestDelay:   2500,
			RateLimitRPM:   25,
		},
	}
}

// LoadConfig loads configuration from environment variables and config files
func LoadConfig() (*Config, error) {
	// Start with defaults
	config := DefaultConfig()

	// Setup viper
	viper.SetConfigName("config")
	viper.SetConfigType("yaml")
	viper.AddConfigPath(".")
	viper.AddConfigPath("./config")
	viper.AddConfigPath("/etc/jobspy-scrapers")

	// Enable environment variable reading
	viper.AutomaticEnv()
	viper.SetEnvKeyReplacer(strings.NewReplacer(".", "_"))

	// Try to read config file (optional)
	if err := viper.ReadInConfig(); err != nil {
		// Config file not found is OK, we'll use env vars and defaults
		if _, ok := err.(viper.ConfigFileNotFoundError); !ok {
			return nil, fmt.Errorf("error reading config file: %w", err)
		}
	}

	// Unmarshal into config struct
	if err := viper.Unmarshal(config); err != nil {
		return nil, fmt.Errorf("error unmarshaling config: %w", err)
	}

	// Override with environment variables
	if err := loadFromEnv(config); err != nil {
		return nil, fmt.Errorf("error loading from environment: %w", err)
	}

	// Validate configuration
	if err := validateConfig(config); err != nil {
		return nil, fmt.Errorf("configuration validation failed: %w", err)
	}

	return config, nil
}

// loadFromEnv loads configuration from environment variables
func loadFromEnv(config *Config) error {
	// Redis configuration
	if redisURL := os.Getenv("REDIS_URL"); redisURL != "" {
		config.RedisURL = redisURL
	}
	if redisPassword := os.Getenv("REDIS_PASSWORD"); redisPassword != "" {
		config.RedisPassword = redisPassword
	}
	if redisDB := os.Getenv("REDIS_DB"); redisDB != "" {
		if db, err := strconv.Atoi(redisDB); err == nil {
			config.RedisDB = db
		}
	}

	// Worker configuration
	if workerID := os.Getenv("WORKER_ID"); workerID != "" {
		config.WorkerID = workerID
	}
	if scraperType := os.Getenv("SCRAPER_TYPE"); scraperType != "" {
		config.ScraperType = scraperType
	}
	if region := os.Getenv("REGION"); region != "" {
		config.Region = region
	}
	if concurrency := os.Getenv("CONCURRENCY"); concurrency != "" {
		if c, err := strconv.Atoi(concurrency); err == nil {
			config.Concurrency = c
		}
	}

	// Proxy configuration
	if proxyPool := os.Getenv("PROXY_POOL"); proxyPool != "" {
		config.ProxyPool = strings.Split(proxyPool, ",")
		for i, proxy := range config.ProxyPool {
			config.ProxyPool[i] = strings.TrimSpace(proxy)
		}
	}

	// Performance tuning
	if maxConns := os.Getenv("MAX_CONNS_PER_HOST"); maxConns != "" {
		if c, err := strconv.Atoi(maxConns); err == nil {
			config.MaxConnsPerHost = c
		}
	}

	// Monitoring
	if logLevel := os.Getenv("LOG_LEVEL"); logLevel != "" {
		config.LogLevel = strings.ToLower(logLevel)
	}
	if metricsEnabled := os.Getenv("METRICS_ENABLED"); metricsEnabled != "" {
		config.MetricsEnabled = strings.ToLower(metricsEnabled) == "true"
	}

	return nil
}

// validateConfig validates the configuration
func validateConfig(config *Config) error {
	if config.RedisURL == "" {
		return fmt.Errorf("redis_url is required")
	}

	if config.ScraperType == "" {
		return fmt.Errorf("scraper_type is required")
	}

	validScraperTypes := []string{"indeed", "linkedin", "glassdoor", "ziprecruiter", "google"}
	isValid := false
	for _, validType := range validScraperTypes {
		if config.ScraperType == validType {
			isValid = true
			break
		}
	}
	if !isValid {
		return fmt.Errorf("invalid scraper_type: %s, must be one of: %v", config.ScraperType, validScraperTypes)
	}

	if config.Concurrency < 1 || config.Concurrency > 100 {
		return fmt.Errorf("concurrency must be between 1 and 100")
	}

	if config.TaskTimeout < 30 || config.TaskTimeout > 3600 {
		return fmt.Errorf("task_timeout must be between 30 and 3600 seconds")
	}

	validLogLevels := []string{"debug", "info", "warn", "error"}
	isValidLogLevel := false
	for _, level := range validLogLevels {
		if config.LogLevel == level {
			isValidLogLevel = true
			break
		}
	}
	if !isValidLogLevel {
		return fmt.Errorf("invalid log_level: %s, must be one of: %v", config.LogLevel, validLogLevels)
	}

	return nil
}

// generateWorkerID generates a unique worker ID
func generateWorkerID() string {
	hostname, _ := os.Hostname()
	if hostname == "" {
		hostname = "unknown"
	}
	pid := os.Getpid()
	return fmt.Sprintf("%s-%d-%d", hostname, pid, time.Now().Unix())
}