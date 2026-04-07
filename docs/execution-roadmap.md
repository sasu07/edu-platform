# Execution Roadmap

## Sprint 1: Student flow polish
- Add `continue where you left off` entry point from hub when an active study session exists.
- Start a study session from the weekly plan with filters preserved.
- Improve study-session error states and empty states.
- Turn the student homepage into an action hub with focus recommendations, quick links, streak, badges, and progress by subiect.
- Add an integrated prep calendar for student and parent dashboards with active days, planned days, and visual streak.
- Verify with frontend build and smoke test.

## Sprint 2: Unify collections
- Align `exercise sets`, `study sessions`, and `variants` around a shared collection model.
- Reuse saved filters and selected exercises across these flows.
- Reduce duplicate API/UI logic for listing, opening, and deleting collections.

## Sprint 3: Guided study loop
- After a session, show stronger recommendations based on weak subiect/topic areas.
- Add direct CTA from history/summary into the next recommended exercise flow.
- Connect study plan entries with generated exercise sets for repeatable practice.

## Sprint 4: Teacher workflow
- Reframe `Import JSON`, `Sources`, and `Exercises` into a single content pipeline.
- Prioritize teacher requests by urgency, age, and ownership.
- Add clearer statuses and timelines for help requests.

## Sprint 5: Parent/Admin clarity
- Add explicit parent-student link statuses and clearer lifecycle messaging.
- Improve admin filters and batch operations.
- Expand progress reporting with trends, not just totals.
