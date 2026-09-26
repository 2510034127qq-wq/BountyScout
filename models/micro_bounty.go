package models

import (
	"github.com/shopspring/decimal"
	"time"
)

// MicroBounty represents a GitHub-based micro bounty opportunity.
// Fields marked as 'unconfirmed' require manual verification.
type MicroBounty struct {
	ID          string          `json:"id" yaml:"id" db:"id"`
	Project     string          `json:"project" yaml:"project" db:"project"`
	IssueURL    string          `json:"issue_url" yaml:"issue_url" db:"issue_url"`
	Title       string          `json:"title" yaml:"title" db:"title"`
	Description string          `json:"description" yaml:"description" db:"description"`
	Reward      decimal.Decimal `json:"reward" yaml:"reward" db:"reward"`
	Currency    string          `json:"currency" yaml:"currency" db:"currency"`
	PaymentMethod string          `json:"payment_method" yaml:"payment_method" db:"payment_method"` // e.g., "USDT", "待确认"
	Deadline    *time.Time      `json:"deadline" yaml:"deadline" db:"deadline"` // nil if unconfirmed
	Status      string          `json:"status" yaml:"status" db:"status"` // "open", "claimed", "resolved"
	Effort      string          `json:"effort" yaml:"effort" db:"effort"` // e.g., "数小时到 1 天"
	Submission  string          `json:"submission" yaml:"submission" db:"submission"` // PR/Issue link
	RelatedPRs  []string        `json:"related_prs" yaml:"related_prs" db:"related_prs"`
	Competition string          `json:"competition" yaml:"competition" db:"competition"` // "未发现明显竞争"
	LastUpdated time.Time       `json:"last_updated" yaml:"last_updated" db:"last_updated"`
	Source      string          `json:"source" yaml:"source" db:"source"` // "GitHub Issue"
	Unconfirmed bool            `json:"unconfirmed" yaml:"unconfirmed" db:"unconfirmed"`
}