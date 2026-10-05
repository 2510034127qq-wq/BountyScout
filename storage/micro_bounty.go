package storage

import (
	"gopkg.in/yaml.v3"
	"os"
	"path/filepath"
	"strings"

	"github.com/2510034127qq-wq/BountyScout/models"
)

// SaveMicroBounties persists bounties to YAML files in the output directory.
func SaveMicroBounties(outputDir string, bounties []*models.MicroBounty, force bool) error {
	if err := os.MkdirAll(outputDir, 0755); err != nil {
		return err
	}

	for _, bounty := range bounties {
		filename := generateFilename(bounty)
		filepath := filepath.Join(outputDir, filename)

		// Check for existing file
		if _, err := os.Stat(filepath); err == nil && !force {
			continue // Skip if exists and force=false
		}

		// Marshal and save
		data, err := yaml.Marshal(bounty)
		if err != nil {
			return err
		}

		if err := os.WriteFile(filepath, data, 0644); err != nil {
			return err
		}
	}

	return nil
}

func generateFilename(bounty *models.MicroBounty) string {
	// Format: {project}-{id}-{status}.yaml
	id := strings.ReplaceAll(bounty.IssueURL, "https://github.com/", "")
	id = strings.ReplaceAll(id, "/", "-")
	id = strings.ReplaceAll(id, "\n", "-")

	status := "open"
	if bounty.Status != "" {
		status = bounty.Status
	}

	return id + ".yaml"
}