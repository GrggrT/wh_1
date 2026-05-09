# Decision Log

## 2026-05-09 — FSM storage choice
**Context:** Need state persistence for shift start/stop flows.
**Options considered:** MemoryStorage, Redis, database-backed.
**Chosen:** MemoryStorage
**Rationale:** Phase 0 is single-user, single-process. MemoryStorage is simplest. Spec says no Redis. FSM state is ephemeral — if bot restarts mid-flow, user can /cancel and retry.
**Reversibility:** trivial

## 2026-05-09 — Geofence boundary behavior
**Context:** Spec §9.6 requires defined behavior for points exactly on polygon edge.
**Options considered:** ST_Contains (exclusive), ST_Covers (inclusive), ST_Intersects.
**Chosen:** ST_Covers (inclusive — point on edge is considered INSIDE)
**Rationale:** Construction workers standing at site boundary should not get warnings. Inclusive is friendlier.
**Reversibility:** trivial

## 2026-05-09 — Hours computation method
**Context:** Spec §10.3 says no float math on time.
**Options considered:** timedelta.total_seconds()/3600.0, Decimal arithmetic on total_seconds.
**Chosen:** Decimal(int(total_seconds)) / Decimal(3600)
**Rationale:** Avoids float precision issues. timedelta gives accurate total_seconds, we convert to int first then use Decimal division.
**Reversibility:** trivial

## 2026-05-09 — Owner guard implementation
**Context:** Need to reject non-owner users at all entry points.
**Options considered:** Middleware, per-router filter, catch-all handler at end.
**Chosen:** Catch-all handler at end of dispatcher + routers only respond to owner.
**Rationale:** In Phase 0, routers are registered first (they match owner commands). The catch-all at the end handles anything else. Simple, no middleware complexity.
**Reversibility:** trivial (switch to middleware in Phase 1 for multi-user)
