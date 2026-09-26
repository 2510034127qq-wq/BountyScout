package tests

import (
	"testing"
	"github.com/2510034127qq-wq/BountyScout/models"
	"github.com/2510034127qq-wq/BountyScout/parsers"
	"github.com/shopspring/decimal"
	"github.com/stretchr/testify/assert"
)

func TestParseMicroBounty(t *testing.T) {
	tests := []struct {
		name     string
		input    string
		want     *models.MicroBounty
		wantErr  bool
	} {
		{
			name: "BasedHardware/omi bounty with $50 reward",
			input: `#### 1. [[Bounty proposal] fix(manual-import): exception text and raw upstream response disclosure in submit-memories ($50 proposed)]
- **Project:** [BasedHardware/omi](https://github.com/BasedHardware/omi)
- **Reward:** $50；US$50
- **Submission:** [Bounty proposal] fix(manual-import): exception text and raw upstream response disclosure in submit-memories ($50 proposed)
- **Last updated:** 2026-09-24T22:06:19Z`,
			want: &models.MicroBounty{
				Project:     "BasedHardware/omi",
				Reward:      decimal.NewFromFloat(50),
				Currency:    "USDT",
				Submission:  "[Bounty proposal] fix(manual-import): exception text and raw upstream response disclosure in submit-memories ($50 proposed)",
				LastUpdated: time.Date(2026, 9, 24, 22, 6, 19, 0, time.UTC),
				Unconfirmed: true,
			},
			wantErr: false,
		},
		{
			name: "StellarLend bounty with unconfirmed reward",
			input: `#### 2. [[BUG BOUNTY] AutoCompoundVault double-transfers deposits/withdrawals, enabling cross-user vault drain after harvest]
- **Project:** [Smartdevs17/stellarlend](https://github.com/Smartdevs17/stellarlend)
- **Reward:** 金额待确认
- **Last updated:** 2026-09-24T21:42:21Z`,
			want: &models.MicroBounty{
				Project:     "Smartdevs17/stellarlend",
				Reward:      decimal.Zero,
				Currency:    "",
				LastUpdated: time.Date(2026, 9, 24, 21, 42, 21, 0, time.UTC),
				Unconfirmed: true,
			},
			wantErr: false,
		},
		{
			name: "Malformed bounty (missing project)",
			input: `#### 3. [Invalid Bounty]
- **Reward:** $100
- **Last updated:** 2026-09-24T00:00:00Z`,
			want:    nil,
			wantErr: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got, err := parsers.ParseMicroBounty(tt.input)
			if (err != nil) != tt.wantErr {
				assert.Equal(t, tt.wantErr, err != nil)
				return
			}
			if tt.wantErr {
				return
			}
			assert.Equal(t, tt.want.Project, got.Project)
			assert.Equal(t, tt.want.Reward, got.Reward)
			assert.Equal(t, tt.want.Currency, got.Currency)
			assert.Equal(t, tt.want.Submission, got.Submission)
			assert.Equal(t, tt.want.LastUpdated, got.LastUpdated)
			assert.Equal(t, tt.want.Unconfirmed, got.Unconfirmed)
		})
	}
}