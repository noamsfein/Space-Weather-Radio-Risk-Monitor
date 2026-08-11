# Test Fixtures

These files are project-created test inputs, not observed NOAA history.

- `invalid_records.jsonl` contains labeled wrappers around invalid raw or canonical records. Tests should pass each nested `record` to the appropriate validator and compare the error with `expected_error`.
- `replay_expected.json` is the deterministic oracle for `kp_replay.jsonl` using an inclusive 15-minute event-time window and a Kp 6 threshold.

The expected replay behavior is:

- 9 Kafka messages consumed;
- 8 unique timestamps accepted;
- 1 duplicate skipped;
- 2 alerts, at `00:10` and `00:27` UTC;
- the Kp 6.3 record remains in the window at exactly `00:25`; and
- the processor rearms at `00:26`, when that record is more than 15 minutes old.
