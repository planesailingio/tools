#!/usr/bin/env python3

import os
import sys
import argparse
import argcomplete
from argcomplete.completers import Completer
from jira import JIRA
from jira.exceptions import JIRAError
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import pytz


def get_jira_client():
    jira_url = os.environ.get("JIRA_URL")
    jira_user = os.environ.get("JIRA_USER")
    jira_token = os.environ.get("JIRA_TOKEN")

    if not all([jira_url, jira_user, jira_token]):
        print("Error: JIRA_URL, JIRA_USER, and JIRA_TOKEN must be set as environment variables.")
        sys.exit(1)

    try:
        return JIRA(server=jira_url, basic_auth=(jira_user, jira_token))
    except JIRAError as e:
        print(f"Error connecting to JIRA: {e}")
        sys.exit(1)


def ticket_completer(prefix, parsed_args, **kwargs):
    jira = get_jira_client()
    try:
        issues = jira.search_issues(
            f'summary ~ "{prefix}*" OR key ~ "{prefix}*" ORDER BY updated DESC',
            maxResults=20,
        )
        return [issue.key for issue in issues]
    except Exception:
        return []


def create_issue(args):
    jira = get_jira_client()

    try:
        issue_dict = {
            "project": {"key": args.project},
            "summary": args.summary,
            "description": args.description,
            "issuetype": {"name": args.issue_type or "Story"},
        }

        issue = jira.create_issue(fields=issue_dict)
        print(f"Issue {issue.key} created.")

        if args.link and args.link_type:
            jira.create_issue_link(type=args.link_type, inwardIssue=issue.key, outwardIssue=args.link)
            print(f"Linked {issue.key} to {args.link} with relationship '{args.link_type}'")

    except JIRAError as e:
        print(f"Failed to create issue: {e}")
        sys.exit(1)


def start_issue(args):
    jira = get_jira_client()

    try:
        transitions = jira.transitions(args.ticket)
        in_progress_id = next(
            (t["id"] for t in transitions if t["name"].lower() == "in progress"), None
        )

        if not in_progress_id:
            print("No 'In Progress' transition found for this issue.")
            sys.exit(1)

        jira.transition_issue(args.ticket, in_progress_id)
        print(f"Issue {args.ticket} transitioned to 'In Progress'.")

    except JIRAError as e:
        print(f"Failed to transition issue: {e}")
        sys.exit(1)


def log_time(args):
    jira = get_jira_client()

    try:
        jira.add_worklog(
            issue=args.ticket,
            timeSpent=args.time,
            comment=args.comment if args.comment else None,
        )
        print(f"Logged {args.time} to {args.ticket}")

    except JIRAError as e:
        print(f"Failed to log time: {e}")
        sys.exit(1)


def stats(args):
    jira = get_jira_client()
    user = jira.current_user()
    now = datetime.now(pytz.utc)

    def get_timeframe(name):
        if name == "this_week":
            start = now - timedelta(days=now.weekday())
        elif name == "last_week":
            start = now - timedelta(days=now.weekday() + 7)
            end = start + timedelta(days=7)
            return start, end
        elif name == "this_month":
            start = now.replace(day=1)
        elif name == "last_month":
            start = (now.replace(day=1) - timedelta(days=1)).replace(day=1)
            end = start + relativedelta(months=1)
            return start, end
        else:
            return now, now
        return start, now

    def format_duration(seconds):
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours}h {minutes}m"

    def sum_worklogs(start, end):
        total = 0
        jql = f"(assignee = {user} OR reporter = {user}) AND updated >= -90d"
        issues = jira.search_issues(jql, maxResults=100)

        for issue in issues:
            try:
                worklogs = jira.worklogs(issue.key)
                for wl in worklogs:
                    if wl.author.name != user:
                        continue
                    started = datetime.strptime(wl.started, "%Y-%m-%dT%H:%M:%S.000%z")
                    if start <= started < end:
                        total += wl.timeSpentSeconds
            except Exception:
                continue

        return total

    timeframes = {
        "This week": get_timeframe("this_week"),
        "Last week": get_timeframe("last_week"),
        "This month": get_timeframe("this_month"),
        "Last month": get_timeframe("last_month"),
    }

    print("JIRA Worklog Stats:\n")
    for label, (start, end) in timeframes.items():
        total_seconds = sum_worklogs(start, end)
        print(f"{label}: {format_duration(total_seconds)}")


def main():
    parser = argparse.ArgumentParser(prog="jira-cli", description="Manage JIRA issues via CLI")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.required = True

    # create
    create_parser = subparsers.add_parser("create", help="Create a new JIRA issue")
    create_parser.add_argument("--project", required=True, help="Project key (e.g., ABC)")
    create_parser.add_argument("--summary", required=True, help="Issue summary")
    create_parser.add_argument("--description", required=True, help="Issue description")
    create_parser.add_argument("--issue-type", default="Story", help="Issue type (default: Story)")
    create_parser.add_argument("--link", help="Link this issue to another (issue key)")
    create_parser.add_argument("--link-type", help="Link type (e.g., blocks, relates to)")
    create_parser.set_defaults(func=create_issue)

    # start
    start_parser = subparsers.add_parser("start", help="Transition issue to In Progress")
    ticket_arg = start_parser.add_argument("--ticket", required=True, help="JIRA issue key")
    ticket_arg.completer = ticket_completer
    start_parser.set_defaults(func=start_issue)

    # logtime
    logtime_parser = subparsers.add_parser("logtime", help="Log time to a JIRA issue")
    ticket_arg2 = logtime_parser.add_argument("--ticket", required=True, help="JIRA issue key")
    ticket_arg2.completer = ticket_completer
    logtime_parser.add_argument("--time", required=True, help="Time spent (e.g., 1h 30m)")
    logtime_parser.add_argument("--comment", help="Worklog comment")
    logtime_parser.set_defaults(func=log_time)

    # stats
    stats_parser = subparsers.add_parser("stats", help="Show logged time stats")
    stats_parser.set_defaults(func=stats)

    argcomplete.autocomplete(parser)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
