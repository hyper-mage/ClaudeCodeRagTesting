# Deferred Items (Phase 06)

## test_record_manager.py::test_check_duplicate_integration
- **Found during:** Plan 06-02 Task 3 full-suite run
- **Status:** Pre-existing fixture error (`user_id` not found) -- exists from module 3 commit c46981a, NOT introduced by Phase 6
- **Scope:** Out of scope for Plan 06-02 (no files in this plan touch record_manager)
- **Resolution:** Future cleanup plan should rename fixture to `test_user_id` or add a local `user_id` fixture to tests/conftest.py
