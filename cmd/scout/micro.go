package main

import (
	"encoding/json"
	"flag"
	"log"
	"os"
	"path/filepath"
	"strings"

	"github.com/2510034127qq-wq/BountyScout/models"
	"github.com/2510034127qq-wq/BountyScout/parsers"
	"github.com/2510034127qq-wq/BountyScout/storage"
)

var (
	inputFile  = flag.String("input", "", "Path to GitHub issue text file or URL")
	outputDir  = flag.String("output", "bounties/micro", "Output directory for YAML files")
	force      = flag.Bool("force", false, "Overwrite existing bounties")
	verbose    = flag.Bool("verbose", false, "Enable debug logging")
)

func main() {
	flag.Parse()

	if *inputFile == "" {
		log.Fatal("input file or URL required")
	}

	// Read input (simplified; real implementation handles URLs/HTML)
	content, err := os.ReadFile(*inputFile)
	if err != nil {
		log.Fatalf("Failed to read input: %v", err)
	}

	// Parse bounties
	bounties, err := parseBounties(string(content))
	if err != nil {
		log.Fatalf("Failed to parse bounties: %v", err)
	}

	// Store bounties
	if err := storage.SaveMicroBounties(*outputDir, bounties, *force); err != nil {
		log.Fatalf("Failed to save bounties: %v", err)
	}

	if *verbose {
		log.Printf("Saved %d micro bounties to %s", len(bounties), *outputDir)
	}
}

func parseBounties(issueText string) ([]*models.MicroBounty, error) {
	var bounties []*models.MicroBounty

	// Split by issue markers (simplified)
	issues := strings.Split(issueText, "#### ")
	for _, issue := range issues[1:] { // Skip header
		bounty, err := parsers.ParseMicroBounty(issue)
		if err != nil {
			if *verbose {
				log.Printf("Skipping invalid bounty: %v", err)
			}
			continue
		}
		bounties = append(bounties, bounty)
	}

	return bounties, nil
}