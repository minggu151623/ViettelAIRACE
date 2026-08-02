# H29 — Token-aligned boundary selector

## Outcome

H29 failed all model-dependent development gates and test was canceled.

- Eligible enumeration coverage: 375/375 (100%, pass).
- Corrupted exact recovery: 139/375 (37.07%, required 70%).
- Unchanged-control retention: 263/375 (70.13%, required 93%).
- Malformed response rate: 1.33% (required 0%).

Diagnosis recovery was highest at 53.98%; symptom was 31.82%, test name
25.71%, test result 24.00%, and drug 0/4. The small drug support is unstable.

On corrupted cases the selector produced 97 spans that strictly contained the
target, 97 that were strictly shorter, 37 shifted spans and five missing/drop
decisions. On unchanged controls, 106/375 correct seeds were unnecessarily
expanded, often into a complete surrounding clause.

This rejects prompt-only boundary repair. The next mechanism should learn BIO
boundary policy from record-held-out weak labels. No test decisions, output ZIP
or competition submission were created.
