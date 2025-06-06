package main

import (
	"context"
	"os"
	"os/signal"
	"syscall"

	"github.com/sirupsen/logrus"

	"github.com/jobspy/scrapers/internal/config"
	"github.com/jobspy/scrapers/internal/redis"
	"github.com/jobspy/scrapers/internal/scraper"
	"github.com/jobspy/scrapers/internal/worker"
)

func main() {
	// Setup logger
	logger := logrus.New()
	logger.SetLevel(logrus.InfoLevel)
	logger.SetFormatter(&logrus.JSONFormatter{})

	logger.Info("Starting Jobspy Go scraper worker")

	// Load configuration
	cfg, err := config.LoadConfig()
	if err != nil {
		logger.WithError(err).Fatal("Failed to load configuration")
	}

	// Set log level from config
	if level, err := logrus.ParseLevel(cfg.LogLevel); err == nil {
		logger.SetLevel(level)
	}

	logger.WithFields(logrus.Fields{
		"worker_id":    cfg.WorkerID,
		"scraper_type": cfg.ScraperType,
		"region":       cfg.Region,
		"concurrency":  cfg.Concurrency,
	}).Info("Configuration loaded")

	// Create Redis client
	redisConfig := &redis.Config{
		URL:      cfg.RedisURL,
		Password: cfg.RedisPassword,
		DB:       cfg.RedisDB,
	}

	redisClient, err := redis.NewClient(redisConfig, logger)
	if err != nil {
		logger.WithError(err).Fatal("Failed to create Redis client")
	}

	// Create scraper factory
	scraperFactory := scraper.NewFactory(logger)

	// Create orchestrator
	orchestrator := worker.NewOrchestrator(cfg, logger, redisClient, scraperFactory)

	// Setup graceful shutdown
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	// Handle shutdown signals
	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)

	// Start orchestrator
	if err := orchestrator.Start(); err != nil {
		logger.WithError(err).Fatal("Failed to start orchestrator")
	}

	logger.Info("Scraper worker started successfully")

	// Wait for shutdown signal
	sig := <-sigCh
	logger.WithField("signal", sig).Info("Received shutdown signal")

	// Graceful shutdown
	logger.Info("Initiating graceful shutdown...")
	if err := orchestrator.Stop(); err != nil {
		logger.WithError(err).Error("Error during shutdown")
	}

	logger.Info("Scraper worker shutdown complete")
}