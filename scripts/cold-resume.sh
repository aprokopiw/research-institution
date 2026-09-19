#!/bin/sh
# scripts/cold-resume.sh — terminal entrypoint for cold-start sessions.
# Wraps `pi "Run @research_institution_orient"` so a fresh agent session
# can pick up where the system left off.

exec pi "Run @research_institution_orient"
