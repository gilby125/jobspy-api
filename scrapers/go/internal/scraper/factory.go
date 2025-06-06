package scraper

import (
	"fmt"

	"github.com/sirupsen/logrus"

	"github.com/jobspy/scrapers/internal/protocol"
	"github.com/jobspy/scrapers/internal/scrapers/jobspy_client"
)

// Factory implements ScraperFactory interface
type Factory struct {
	logger *logrus.Logger
}

// NewFactory creates a new scraper factory
func NewFactory(logger *logrus.Logger) *Factory {
	return &Factory{
		logger: logger,
	}
}

// CreateScraper creates a scraper instance based on type
func (f *Factory) CreateScraper(scraperType protocol.ScraperType, config ScraperConfig) (Scraper, error) {
	f.logger.WithFields(logrus.Fields{
		"scraper_type": scraperType,
		"worker_id":    config.WorkerID,
	}).Debug("Creating JobSpy API client instance")

	switch scraperType {
	case protocol.ScraperTypeIndeed:
		return f.createJobSpyClient(config, "indeed")
	case protocol.ScraperTypeLinkedIn:
		return f.createJobSpyClient(config, "linkedin")
	case protocol.ScraperTypeGlassdoor:
		return f.createJobSpyClient(config, "glassdoor")
	case protocol.ScraperTypeZipRecruiter:
		return f.createJobSpyClient(config, "ziprecruiter")
	case protocol.ScraperTypeGoogle:
		return f.createJobSpyClient(config, "google")
	default:
		return nil, fmt.Errorf("unsupported scraper type: %s", scraperType)
	}
}

// GetSupportedTypes returns list of supported scraper types
func (f *Factory) GetSupportedTypes() []protocol.ScraperType {
	return []protocol.ScraperType{
		protocol.ScraperTypeIndeed,
		protocol.ScraperTypeLinkedIn,
		protocol.ScraperTypeGlassdoor,
		protocol.ScraperTypeZipRecruiter,
		protocol.ScraperTypeGoogle,
	}
}

// createJobSpyClient creates a JobSpy API client for any scraper type
func (f *Factory) createJobSpyClient(config ScraperConfig, scraperName string) (Scraper, error) {
	// Apply JobSpy API client defaults
	clientConfig := config
	if clientConfig.BaseURL == "" {
		// Default to local JobSpy API instance
		clientConfig.BaseURL = "http://localhost:8000"
	}
	if clientConfig.ResponseTimeout == 0 {
		clientConfig.ResponseTimeout = 60 // 60 second timeout for JobSpy API calls
	}
	if clientConfig.MaxIdleConns == 0 {
		clientConfig.MaxIdleConns = 10
	}
	if clientConfig.MaxConnsPerHost == 0 {
		clientConfig.MaxConnsPerHost = 10
	}

	// Set API key if provided (stored in UserAgents field for simplicity)
	if len(clientConfig.UserAgents) == 0 {
		clientConfig.UserAgents = []string{""} // Empty API key by default
	}

	client := jobspy_client.NewJobSpyAPIClient(clientConfig, f.logger)
	if err := client.Configure(clientConfig); err != nil {
		return nil, fmt.Errorf("failed to configure JobSpy API client for %s: %w", scraperName, err)
	}

	f.logger.WithFields(logrus.Fields{
		"api_url":      clientConfig.BaseURL,
		"scraper_type": scraperName,
	}).Info("JobSpy API client created")
	return client, nil
}

