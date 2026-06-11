# Context File Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add `madcli run --context-file` so callers can attach existing markdown files to a run context package.

**Architecture:** Keep context packaging in `madcli/context.py`; keep CLI parsing and preflight validation in `madcli/cli.py`. Copy source files into `.madcli/runs/<run-id>/context/` so run artifacts remain durable if the original file changes or is deleted.

**Tech Stack:** Python 3.11 standard library, `argparse`, `unittest`.

---

### Task 1: Context Package Support

**Files:**
- Modify: `madcli/context.py`
- Test: `tests/test_context.py`

**Step 1: Write the failing test**

Add a test that creates a temporary markdown file, calls `write_context_package(..., extra_context_files=[source])`, and asserts a copied file named `context_file_1_<source-name>` exists in the context directory with the original content and source path heading.

**Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_context.ContextTests.test_write_context_package_copies_context_files -v`
Expected: FAIL because `extra_context_files` is not accepted yet.

**Step 3: Write minimal implementation**

Extend `write_context_package` with an optional `extra_context_files` parameter. For each source file, read UTF-8 text and write a durable copied markdown file into the context directory.

**Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_context.ContextTests.test_write_context_package_copies_context_files -v`
Expected: PASS.

### Task 2: CLI Flag Support

**Files:**
- Modify: `madcli/cli.py`
- Create: `tests/test_cli.py`
- Modify: `README.md`

**Step 1: Write the failing test**

Add a dry-run CLI test that passes `--context-file <markdown-file>` and asserts the generated run context directory contains the copied file.

**Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_cli.CliTests.test_run_dry_run_copies_context_file -v`
Expected: FAIL because the parser does not know `--context-file`.

**Step 3: Write minimal implementation**

Add repeatable `--context-file` parsing, validate each path before creating a run, and pass resolved paths into `write_context_package`.

**Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_cli.CliTests.test_run_dry_run_copies_context_file -v`
Expected: PASS.

### Task 3: Full Verification

**Files:**
- All touched files

**Step 1: Run all tests**

Run: `python -m unittest discover -s tests -v`
Expected: all tests pass.

**Step 2: Run CLI smoke test**

Run the documented dry-run flow with a temporary config and context file, then remove generated artifacts.
