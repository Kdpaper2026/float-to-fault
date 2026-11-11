# Protocol v1 — attribution vs mitigation (frozen 2026-10-28 before any held-out run)

## Question
Does a Shapley-ranked attribution of delay point to the best feasible fixes at a decision epoch, and where does it not?  (RQ1–RQ4 of the proposal.)

## Instances
RCPLIB 'original' instances with #Act in {30, 60, 90, 120} and at least one resource of capacity >= 2.  Split by SHA-256 of the instance name: even first byte parity -> DEVELOPMENT, odd -> HELD-OUT.  Development is used for debugging and for choosing nothing that the held-out run reports.  Quotas: development 40 per size; held-out 100 per size (400 instances).  Held-out is run once per configuration after this protocol is frozen; any change after seeing held-out output is recorded as an amendment at the end of this file.

## Execution model
Baseline-sequence serial scheduler with no overtaking (each job starts no earlier than the previous job in the sequence, after predecessors, release time and resource capacity).  The baseline schedule is the model's own no-event schedule, with priority list by latest finish time (ties by topological index).  Monotonicity (adding an event never shortens the finish) is tested on every instance for all masks; instances failing are reported and excluded.

## Events (K = 8 per instance, typed, owner-labelled)
design_hold, site_access (owner: release time); approval_wait (authority: release time, empirical NYC DOB NOW lead distribution scaled to project weeks); supply_delay (contractor: release time); productivity, rework (contractor: job extension); labour (contractor: one unit of a resource lost in a window); weather (neutral: extensions of jobs starting in a window; not fixable).  Sizes and type probabilities are ASSUMPTIONS and are swept (below).  Primary mix: design_hold .18, site_access .09, approval_wait .18, supply_delay .10, productivity .13, rework .09, labour .13, weather .10.

## Attribution (E1)
Players = the 8 events.  v(S) = M(S) - M(empty).  Exact Shapley over 256 subsets.  Compared with but-for, alone, chronological windows, and logic-only CPM (event counted at nominal size if its job lies on the precedence-only critical path).  Ledger variant: weather held fixed in every coalition (E_f), giving planned finish, fixed-event reference, full modelled finish, attributed delay.
Metrics (all defined per project, then averaged over projects unless 'pooled'):
- CPM zero-share (pooled): total Shapley days in events CPM scores 0 / total delay days.
- CPM claim ratio (pooled): total CPM-claimed days / total delay days.
- Fix-first efficiency at k = 1, 2, 3: delay removed by removing a method's top-k events from the full schedule / best k-set (retrospective, full information; NOT the prospective test).

## Prospective mitigation (E2)
Decision epoch t = tau * M(all events), tau in {0.25, 0.5, 0.75} (primary 0.5).  Realised schedule S_all (all events).  Jobs with S_all < t are committed: pinned at their realised start and realised duration in every counterfactual (fixed-commitment).
Fix model: each fixable event e (all but weather) has a fix that removes its effect on jobs whose realised start is >= t + lead_e (release events: release removed; extension events: extension removed; labour: the loss is removed from t + lead_e on).  lead_e = 0 for owner/contractor events; lead_e = L_auth * M0 for approval_wait and for design review events typed authority (primary L_auth = 0.10).  Fix cost K_e = size_e * exp(sigma * z_e), z ~ N(0,1), size_e = nominal days (labour: window length); primary sigma = 0.5.  Budget B = beta * sum of K_e over fixable events, primary beta = 0.5.
Value of a fix set A: R(A) = M(all, no fix) - M(all, fixes A applied) under the pinned commitments.  Primary objective: days recovered within budget.  (Monetary net value is NOT run in v1; recorded as a limitation.)
Policies (identical observed events, costs, budget, leads; none sees future realisations):
 P1 frequency: rank fixable observed events by survey weight of the event type (sum of Pereira et al. 2024 ICG of mapped causes, Appendix A of the proposal); fill budget in rank order, skipping unaffordable.
 P2 Shapley: rank fixable observed events by Shapley share computed on the analyst's model (observed events); fill budget in rank order.
 P3 direct greedy: repeatedly pick the fixable observed event with the highest marginal R per unit cost in the analyst's pinned model; stop at budget or no gain.
 P4 exact: best subset within budget in the analyst's pinned model (all subsets enumerated).
 ORACLE: best subset within budget in the TRUE model (benchmark only; equals P4 under complete evidence).
Every chosen set is scored in the TRUE model.  Outcomes per instance: R_true, capture = R_true / R_oracle, regret = R_oracle - R_true (instances with R_oracle = 0 excluded and counted), set agreement P2 vs P4 (identical sets; same first pick).

## Evidence regimes (factor separate from policy)
 a complete;  b random omission m = 0.3;  c optimistic extraction: recall .91, precision .91 (phantom events), size noise lognormal sigma .2;  d pessimistic extraction: recall .50, precision .80, size noise sigma .5.
(recall/precision anchors: Pal et al. 2024 and Gundidza et al. 2026 as read; these are assumptions about a future pipeline, not measurements.)
Attribution stability (E3): for regimes b–d, error in the owner+authority share of attributed delay vs the true share, and whether the leading party (owner / authority / contractor / neutral by Shapley share) changes.

## Sensitivity (held-out, N = 100 per configuration, one factor at a time vs primary)
event size scale {0.5, 2}; mix {owner-heavy, contractor-heavy}; tau {0.25, 0.75}; L_auth {0, 0.25}; sigma {0, 1}; beta {0.25, 0.75}.

## Statistics
Paired by instance.  Report means with 95% bootstrap CIs (2,000 resamples over instances), effect sizes as differences in capture.  No hypothesis is declared 'supported' on development data.  Hypothesis readings (pre-specified):
 H1: resource-aware vs logic-only attribution differ materially: CPM zero-share >= 0.30 pooled in primary config.
 H2: moderate extraction error changes the leading party in a non-trivial fraction: >= 10% of instances under regime d.
 H3: P2 agrees with P4 (same set) in a majority of instances in the primary configuration; divergence concentrates (capture of P2 minus P4 most negative) where resources bind / approval leads long / cost spread large.
 H4: with L_auth = 0.25 the capture of P2 falls by >= 5 points relative to L_auth = 0.
Outcomes that contradict a hypothesis are reported as such.

## Amendments
A1 (2026-10-28, before any held-out run; engine proved to run in ~0.3 s per instance): held-out primary run uses 200 instances per size (800 total) instead of 100; development run uses 100 per size; sensitivity configurations (size, mix) use 100 per size on the held-out split.  Nothing else changed.

A2 (2026-10-28, after the development run, before any held-out run).  Development output showed (i) P2 ignores fix cost whereas P3/P4 use it, and (ii) P2 uses a whole-project retrospective Shapley whereas the decision is taken at epoch t.  To avoid a straw-man comparison, three variants are ADDED (the original P1-P4 and all metrics are unchanged):
  P2b: Shapley (retrospective, as P2) ranked by share per unit fix cost.
  P2e: Shapley computed in the pinned model at the epoch (attribution of the remaining delay given commitments), ranked by share.
  P2eb: P2e ranked by share per unit fix cost.
(ii) Development also showed that 'same fix set as P4' is dominated by budget padding (rank policies fill the budget with events that add no recovery) and is therefore a poor measure of agreement.  The pre-specified H3 is kept and reported as specified; a companion H3b is ADDED: P2 achieves at least 99% of the oracle recovery in a majority of instances with recoverable delay, plus the mean capture gap to P3/P4.  No threshold or hypothesis was changed after seeing held-out output.

A3 (2026-10-28, after the development runs, before any held-out run).  Added configuration 'partial': each fixable event has a fix effectiveness phi_e ~ U(0.3, 1.0) (fraction of the event's remaining effect removed; release events: remaining delay shortened by phi; extension events: amount reduced by phi; labour: remaining window shortened by phi); the analyst knows phi (phantom events: 0.65).  Primary configuration keeps phi = 1 and was verified to give results identical to the pre-A3 development run.  Held-out run list (each run once): primary (200 per size); partial, size_lo, size_hi, mix_owner, mix_contr (100 per size).  Analysis script exp_analyze.py is final as of this entry.

## Amendment A4 (post-hoc, exploratory; written after all held-out primary and sensitivity analyses were seen)
Held-out hypotheses H1-H4/H3b are closed and are not re-tested. A4 adds two exploratory analyses, reported as such and not as confirmatory:
 (i)  Extraction-error sweep: recall in {.5,.7,.9} x precision in {.6,.8,1.0} x size-noise sigma in {0,.25,.5} (27 cells) at tau .5, L_auth .10, cost sigma .5, budget beta .5. Fresh instance sample from the held split (seed 20261101, 80 per size; overlap with earlier held instances is possible).
 (ii) Money objective: net value = rho * (days recovered in the true model) - (spent cost), rho (value of a delay day in units of the cost of removing one day of event size) in {1.5, 3, 6}. Rank policies spend the whole budget as before. Net-value-aware policies: greedy stopping at non-positive marginal net value in the analyst's model (P3n), exact net-value maximiser in the analyst's model within budget (P4n). Oracle: best net value in the true model within budget (>= 0, empty set allowed).
 Reported: mean net value, capture of oracle net value (ratio of sums), share of instances with negative net value.
 Rates in (i) are assumptions about a future extraction pipeline, not measurements.
 Note added during A4 (before its results were read): the first money-objective run showed that rank policies forced to spend the whole budget lose money by construction, a straw man. Two stop-rule variants were therefore ADDED and the run repeated with identical seeds: P1s (survey-frequency order) and P2es (epoch-Shapley order), each skipping a fix whose net value in the analyst's model is not positive. The days-objective results of (i) are unchanged by this repeat.

## Amendment A5 (post-hoc, exploratory): DSLIB real-schedule replay
Not part of the frozen protocol. real/dslib_replay.py replays 163 DSLIB construction projects with each project's own calendar (Agenda sheet), baseline dates and logic, and the actual starts and durations of the last tracking sheet. Delay is decomposed by a two-player Shapley value: D = actual vs baseline activity durations, W = actual vs baseline start waits (start minus logic-ready time). Coalition finishes use the same forward pass; the planned and actual coalitions reproduce the file's planned and reported real duration. Screens (set after seeing replay diagnostics, not outcome shares): (1) at most 5% of activities start before their logic permits in the baseline; (2) replayed real duration within 0.5 working day of the file-reported real duration. Primary set = both screens. DSLIB has no causes or responsible parties; W is waiting of any origin (owner, authority, contractor, resources, planned waits). real/dslib_resource_check.py tests whether a baseline-order serial scheduler with renewable-resource limits reproduces baseline starts.

## Note A6 (post-hoc): anchoring of the extraction regimes to published evaluations
The regimes were fixed before the held-out runs as assumptions. Afterwards the source papers were read for what they actually measured. Gundidza et al. (2026, BDCC 10, 269), independent three-annotator adjudicated gold on development-bank road reports: event-detection precision 0.795 (116/146), chunk-level recall 0.50 (5/10 chunks, Wilson 95% CI 0.24-0.76), 15-way cause accuracy 0.50, human inter-annotator kappa on cause 0.27-0.43. This matches regime d (recall .50, precision .80). Pal et al. (2024, CIB W78): average precision 0.91 and recall 0.97 for classifying 157 already-identified delay issues into ten categories (one project, two buildings); a classification task, so regime c is an optimistic reference and not a measured event-discovery recall. Size noise has no published anchor. No regime values were changed.

## Amendment A7 (post-hoc, exploratory; written before the litigation run, after all earlier held-out analyses were seen)
Reason: court litigation can itself stop work and is a recognised delay cause that the eight primary event types omit. Frozen files (exp_engine.py, exp_run.py, exp_analyze.py) are not edited; exp_lit.py patches the event compiler at run time.
Event: one 'litigation' event (owner class 'court'; independent of the parties' conduct, i.e. a third-party or court-ordered stay) is added to the eight primary events (K = 9). Window start a ~ U(0.1, 0.6) x M0; length w = scale x U(0.05, 0.20) x M0; every real job whose baseline start is >= a gets release time a + w (jobs in progress continue). Fixable only by settlement or vacation of the order: fix removes the release for jobs starting at or after t + lead; lead L_lit x M0 (primary 0.25); cost w x exp(sigma z) x cost multiplier (primary 1). Survey weight for the frequency policy is a floor of 0.5 (no published weight). Disputes that are consequences of a party's conduct are NOT modelled (they would double count the root cause); this is a stated limit.
Design: same 8 events, costs and seeds as the primary configuration, evaluated twice per instance (8 events; 9 events), tau .5, L_auth .10, sigma .5, beta .5. Regimes: a complete; lo = every event recorded except the litigation event; c; d. Held-out split, fresh sample (seed 20261102), 100 per size primary; sweeps 50 per size: stoppage scale {0.5, 2}, L_lit {0.10, 0.50}, cost multiplier 3.
Pre-specified readings (no threshold changed after the run):
 HL1: if the litigation event is missing from the record (lo), the leading party differs from the true leading party in >= 10% of instances where the litigation event is present.
 HL2: with the litigation event in a complete record, the epoch Shapley policy (P2e) still captures >= 0.95 of the oracle recovery and stays within 0.03 of the exact policy P4.
 HL3: with L_lit 0.50 the litigation event is part of the oracle best set in a smaller share of instances than with L_lit 0.10.
Reported: pooled share of attributed delay by party (incl. court), leading party under truth, paired change in other parties' shares between the 8-event and 9-event worlds, capture by policy and regime with bootstrap CIs over instances.
