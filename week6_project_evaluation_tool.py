#!/usr/bin/env python3
"""
Week 6 – Final Project Evaluation Helper
----------------------------------------
A small SQLite-backed command-line tool for tracking evaluation KPIs and
future-roadmap actions for a hypothetical software project.

Requirements: Python 3.9+ (standard library only).

Examples:
    python week6_project_evaluation_tool.py init
    python week6_project_evaluation_tool.py add-kpi --name "Automated test pass rate" --target 98 --actual 96 --unit percent --notes "Illustrative"
    python week6_project_evaluation_tool.py list-kpis
    python week6_project_evaluation_tool.py add-action --title "Automate critical journeys" --owner "QA / Developer" --priority high --due 2027-01-15
    python week6_project_evaluation_tool.py list-actions
    python week6_project_evaluation_tool.py update-action 1 --status in_progress
    python week6_project_evaluation_tool.py summary

All values entered for a sample project should be labelled appropriately.
This tool does not connect to external systems and does not verify project data.
"""

from __future__ import annotations

import argparse
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).with_name("week6_project_evaluation.db")
PRIORITIES = ("low", "medium", "high", "critical")
STATUSES = ("planned", "in_progress", "blocked", "done", "cancelled")


def connect() -> sqlite3.Connection:
    """Open the local database and ensure rows can be accessed by column name."""
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialise() -> None:
    """Create the KPI and roadmap-action tables if they do not already exist."""
    with connect() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS kpis (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                target REAL NOT NULL,
                actual REAL,
                unit TEXT NOT NULL DEFAULT '',
                notes TEXT NOT NULL DEFAULT '',
                recorded_at TEXT NOT NULL
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS roadmap_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                owner TEXT NOT NULL DEFAULT 'Unassigned',
                priority TEXT NOT NULL CHECK(priority IN
                    ('low', 'medium', 'high', 'critical')),
                status TEXT NOT NULL DEFAULT 'planned' CHECK(status IN
                    ('planned', 'in_progress', 'blocked', 'done', 'cancelled')),
                due_date TEXT,
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            )
        """)
    print(f"Database ready: {DB_PATH}")


def validate_date(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "Date must use YYYY-MM-DD format."
        ) from exc


def add_kpi(args: argparse.Namespace) -> None:
    initialise()
    with connect() as db:
        cur = db.execute(
            """INSERT INTO kpis
               (name, target, actual, unit, notes, recorded_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (args.name, args.target, args.actual, args.unit, args.notes,
             datetime.now().isoformat(timespec="seconds"))
        )
        print(f"KPI recorded with ID {cur.lastrowid}.")


def list_kpis(_: argparse.Namespace) -> None:
    initialise()
    with connect() as db:
        rows = db.execute("SELECT * FROM kpis ORDER BY id").fetchall()
    if not rows:
        print("No KPIs recorded yet.")
        return
    print(f"{'ID':<4} {'KPI':<32} {'Target':>10} {'Actual':>10} {'Unit':<12}")
    print("-" * 72)
    for row in rows:
        actual = "N/A" if row["actual"] is None else f'{row["actual"]:g}'
        print(f'{row["id"]:<4} {row["name"][:31]:<32} '
              f'{row["target"]:>10g} {actual:>10} {row["unit"]:<12}')
        if row["notes"]:
            print(f'     Notes: {row["notes"]}')


def add_action(args: argparse.Namespace) -> None:
    initialise()
    due = validate_date(args.due)
    with connect() as db:
        cur = db.execute(
            """INSERT INTO roadmap_actions
               (title, owner, priority, status, due_date, notes, created_at)
               VALUES (?, ?, ?, 'planned', ?, ?, ?)""",
            (args.title, args.owner, args.priority, due, args.notes,
             datetime.now().isoformat(timespec="seconds"))
        )
        print(f"Roadmap action recorded with ID {cur.lastrowid}.")


def list_actions(args: argparse.Namespace) -> None:
    initialise()
    query = "SELECT * FROM roadmap_actions"
    params = ()
    if args.status:
        query += " WHERE status = ?"
        params = (args.status,)
    query += " ORDER BY CASE priority WHEN 'critical' THEN 1 " \
             "WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END, id"
    with connect() as db:
        rows = db.execute(query, params).fetchall()
    if not rows:
        print("No matching roadmap actions.")
        return
    print(f"{'ID':<4} {'Priority':<10} {'Status':<12} {'Due':<12} "
          f"{'Owner':<20} Title")
    print("-" * 100)
    for row in rows:
        print(f'{row["id"]:<4} {row["priority"]:<10} {row["status"]:<12} '
              f'{(row["due_date"] or "-"):<12} {row["owner"][:19]:<20} '
              f'{row["title"]}')
        if row["notes"]:
            print(f'     Notes: {row["notes"]}')


def update_action(args: argparse.Namespace) -> None:
    initialise()
    with connect() as db:
        cur = db.execute(
            "UPDATE roadmap_actions SET status = ? WHERE id = ?",
            (args.status, args.action_id)
        )
        if cur.rowcount == 0:
            print(f"No roadmap action found with ID {args.action_id}.")
        else:
            print(f"Action {args.action_id} updated to {args.status}.")


def summary(_: argparse.Namespace) -> None:
    initialise()
    with connect() as db:
        kpi_count = db.execute("SELECT COUNT(*) FROM kpis").fetchone()[0]
        action_rows = db.execute(
            "SELECT status, COUNT(*) AS count FROM roadmap_actions GROUP BY status"
        ).fetchall()
        priority_rows = db.execute(
            "SELECT priority, COUNT(*) AS count FROM roadmap_actions GROUP BY priority"
        ).fetchall()
    status_counts = {row["status"]: row["count"] for row in action_rows}
    priority_counts = {row["priority"]: row["count"] for row in priority_rows}
    total_actions = sum(status_counts.values())
    completed = status_counts.get("done", 0)
    completion = (completed / total_actions * 100) if total_actions else 0.0

    print("\nPROJECT EVALUATION SUMMARY")
    print("=" * 32)
    print(f"KPIs recorded: {kpi_count}")
    print(f"Roadmap actions: {total_actions}")
    print(f"Completed actions: {completed}")
    print(f"Action completion: {completion:.1f}%")
    print("\nActions by status:")
    for status in STATUSES:
        print(f"  {status:<12} {status_counts.get(status, 0)}")
    print("\nActions by priority:")
    for priority in PRIORITIES:
        print(f"  {priority:<12} {priority_counts.get(priority, 0)}")
    print("\nReminder: recorded values are only as reliable as the evidence entered.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Track project evaluation KPIs and roadmap actions."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="Create the local database.")

    p_kpi = sub.add_parser("add-kpi", help="Record an evaluation KPI.")
    p_kpi.add_argument("--name", required=True)
    p_kpi.add_argument("--target", required=True, type=float)
    p_kpi.add_argument("--actual", type=float, default=None)
    p_kpi.add_argument("--unit", default="")
    p_kpi.add_argument("--notes", default="")
    p_kpi.set_defaults(func=add_kpi)

    p_list_kpi = sub.add_parser("list-kpis", help="List recorded KPIs.")
    p_list_kpi.set_defaults(func=list_kpis)

    p_action = sub.add_parser("add-action", help="Add a roadmap action.")
    p_action.add_argument("--title", required=True)
    p_action.add_argument("--owner", default="Unassigned")
    p_action.add_argument("--priority", choices=PRIORITIES, default="medium")
    p_action.add_argument("--due", help="Due date in YYYY-MM-DD format.")
    p_action.add_argument("--notes", default="")
    p_action.set_defaults(func=add_action)

    p_list_action = sub.add_parser("list-actions", help="List roadmap actions.")
    p_list_action.add_argument("--status", choices=STATUSES)
    p_list_action.set_defaults(func=list_actions)

    p_update = sub.add_parser("update-action", help="Change an action's status.")
    p_update.add_argument("action_id", type=int)
    p_update.add_argument("--status", required=True, choices=STATUSES)
    p_update.set_defaults(func=update_action)

    p_summary = sub.add_parser("summary", help="Show a project tracking summary.")
    p_summary.set_defaults(func=summary)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "init":
        initialise()
    else:
        args.func(args)


if __name__ == "__main__":
    main()
