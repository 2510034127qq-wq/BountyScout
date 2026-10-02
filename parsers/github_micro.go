package parsers

import (
	"errors"
	"github.com/2510034127qq-wq/BountyScout/models"
	"github.com/shopspring/decimal"
	"regexp"
	"strings"
	"time"
)

var (
	rewardRegex    = regexp.MustCompile(`\$?\d+\.?\d*|金额待确认`)
	currencyRegex  = regexp.MustCompile(`US\$|\$|待确认`)
	dateRegex      = regexp.MustCompile(`\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2}Z`)
	effortRegex    = regexp.MustCompile(`几十分钟|数小时|1 天|待确认`)
)

// ParseMicroBounty extracts structured data from GitHub issue text.
func ParseMicroBounty(issueText string) (*models.MicroBounty, error) {
	bounty := &models.MicroBounty{Unconfirmed: true}

	// Extract metadata (simplified; real implementation uses HTML parsing)
	lines := strings.Split(issueText, "\n")
	for _, line := range lines {
		if strings.Contains(line, "**Project:**") {
			bounty.Project = extractField(line, "Project:")
		} else if strings.Contains(line, "**Reward:**") {
			bounty.Reward, bounty.Currency = extractReward(line)
		} else if strings.Contains(line, "**Deadline:**") {
			bounty.Deadline = extractDeadline(line)
		} else if strings.Contains(line, "**Submission:**") {
			bounty.Submission = extractField(line, "Submission:")
		} else if strings.Contains(line, "**Last updated:**") {
			bounty.LastUpdated = extractTimestamp(line)
		}
	}

	// Validate required fields
	if bounty.Project == "" || bounty.Reward.IsZero() {
		return nil, errors.New("missing required fields: project or reward")
	}

	return bounty, nil
}

func extractField(line, prefix string) string {
	parts := strings.Split(line, prefix)
	if len(parts) < 2 {
		return ""
	}
	return strings.TrimSpace(strings.TrimPrefix(parts[1], ":"))
}

func extractReward(line string) (decimal.Decimal, string) {
	parts := strings.Split(line, ":")
	if len(parts) < 2 {
		return decimal.Zero, ""
	}

	value := strings.TrimSpace(parts[1])
	match := rewardRegex.FindString(value)
	if match == "" {
		return decimal.Zero, ""
	}

	// Handle currency
	currency := "USDT" // default
	currencyMatch := currencyRegex.FindString(value)
	if currencyMatch != "" {
		currency = strings.ReplaceAll(currencyMatch, "US", "")
		currency = strings.ReplaceAll(currency, "$", "")
		if currency == "待确认" {
			currency = ""
		}
	}

	// Parse amount
	amount, err := decimal.NewFromString(strings.ReplaceAll(match, "$", ""))
	if err != nil {
		amount = decimal.Zero
	}

	return amount, currency
}

func extractDeadline(line string) *time.Time {
	match := dateRegex.FindString(line)
	if match == "" {
		return nil
	}
	parsed, err := time.Parse(time.RFC3339, match)
	if err != nil {
		return nil
	}
	return &parsed
}

func extractTimestamp(line string) time.Time {
	match := dateRegex.FindString(line)
	if match == "" {
		return time.Now()
	}
	parsed, _ := time.Parse(time.RFC3339, match)
	return parsed
}