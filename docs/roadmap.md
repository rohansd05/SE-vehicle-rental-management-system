# VRMS — Roadmap from 16 Oct 2026

Eight modules, four per developer, built in parallel. Ownership of apps and
frontend features is in `docs/CLAUDE.md` ("Ownership from 16 Oct 2026").
Use case numbers follow Exp 2 (`docs/experiments/AC_2024300049_ROHAN_SE_EXP2.pdf`);
business rules are BR-1 to BR-16 of the SRS (Section 5.5).

## Modules

| Module | Use cases | Business rules | Owner | Dates (2026) |
|---|---|---|---|---|
| R1 Payments completion | UC 13 Approve Refund | BR-4, BR-9, BR-14 (provides the refund/capture/due services R2 and N2 use) | Rohan Dhumal | 16 to 18 Oct |
| N1 Handover | UC 7 Handover Vehicle | BR-2, BR-3 (re-checked at handover) | Nidhi Rajkamal Dhyani | 16 to 18 Oct |
| R2 Modify/Cancel/Extend | UC 4 Modify / Cancel Booking | BR-1, BR-5, BR-6, BR-8 | Rohan Dhumal | 19 to 21 Oct |
| N2 Return and settlement | UC 8 Return Vehicle | BR-10, BR-11, BR-12, BR-14 (via R1's refund_deposit) | Nidhi Rajkamal Dhyani | 19 to 21 Oct |
| R3 Reports and booking notifications | UC 14 View Reports | none | Rohan Dhumal | 21 to 23 Oct |
| N3 Admin console and maintenance completion | UC 9, UC 10 (completion), UC 11 Manage Fleet and Tariffs, UC 12 Manage Users and Blacklist | BR-4 (blacklist), BR-13 (screens), BR-15, BR-16 | Nidhi Rajkamal Dhyani | 21 to 23 Oct |
| R4 Catalogue, rating, doorstep delivery | UC 2 Search Vehicles, UC 6 Rate Vehicle | BR-7 (plus D13 for ratings) | Rohan Dhumal | 23 to 24 Oct |
| N4 Deployment and PWA | None (OE-2, OE-4, CO-1) | none (D1, D8, OE-2, OE-4, CO-1) | Nidhi Rajkamal Dhyani | 23 to 24 Oct |

## Milestones

| Date | Milestone |
|---|---|
| 25 Oct 2026 | Code freeze |
| 27 Oct 2026, 9:00 am | Exp 8 (RMMM plan) and Exp 10 (test cases and unit testing) due |

## Rules while the modules run

- Only the owner adds migrations to an app.
- Cross-module calls go through the owner's `services.py` functions (for
  example, every vehicle status change goes through
  `apps/fleet/services/status.py`).
