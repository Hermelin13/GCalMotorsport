#!/usr/bin/env python3
"""Launcher to run F1/FE/WEC calendar scripts together or individually.

Usage (interactive): run without args and follow prompts.
Usage (non-interactive):
  python run_calendars.py --which all --f1-year 2026 --fe-season 2025-26 --wec-year 2026 --dry-run
"""
from __future__ import annotations

import argparse
import shlex
import subprocess
from typing import List


def build_commands(which: List[str], f1_year: int, fe_season: str, wec_year: int, upload: bool, dry_run: bool, calid: str | None, creds: str | None) -> List[List[str]]:
    cmds = []
    if 'f1' in which:
        cmd = ['python', 'f1_calendar.py', str(f1_year)]
        if upload and not dry_run:
            cmd.append('--upload')
            if calid:
                cmd += ['--calendar-id', calid]
            if creds:
                cmd += ['--creds', creds]
        cmds.append(cmd)
    if 'fe' in which:
        cmd = ['python', 'fe_calendar.py', fe_season]
        if upload and not dry_run:
            cmd.append('--upload')
            if calid:
                cmd += ['--calendar-id', calid]
            if creds:
                cmd += ['--creds', creds]
        if dry_run:
            cmd.append('--dry-run')
        cmds.append(cmd)
    if 'wec' in which:
        cmd = ['python', 'wec_calendar.py', str(wec_year)]
        if upload and not dry_run:
            cmd.append('--upload')
            if calid:
                cmd += ['--calendar-id', calid]
            if creds:
                cmd += ['--creds', creds]
        cmds.append(cmd)
    return cmds


def interactive_menu() -> List[str]:
    print('Select which calendars to run:')
    print('  1) All (F1, FE, WEC)')
    print('  2) F1 only')
    print('  3) FE only')
    print('  4) WEC only')
    sel = input('Choice (1-4): ').strip()
    if sel == '1':
        return ['f1', 'fe', 'wec']
    if sel == '2':
        return ['f1']
    if sel == '3':
        return ['fe']
    if sel == '4':
        return ['wec']
    print('Invalid choice, defaulting to all')
    return ['f1', 'fe', 'wec']


def main():
    p = argparse.ArgumentParser(description='Launcher for calendar scripts')
    p.add_argument('--which', help='Comma-separated: all,f1,fe,wec', default=None)
    p.add_argument('--f1-year', type=int, default=2026)
    p.add_argument('--fe-season', default='2025-26')
    p.add_argument('--wec-year', type=int, default=2026)
    p.add_argument('--upload', action='store_true')
    p.add_argument('--dry-run', action='store_true')
    p.add_argument('--calendar-id', default=None)
    p.add_argument('--creds', default='calendarcred.json')
    args = p.parse_args()

    if args.which:
        parts = [w.strip().lower() for w in args.which.split(',')]
        if 'all' in parts:
            which = ['f1', 'fe', 'wec']
        else:
            which = [p for p in parts if p in ('f1', 'fe', 'wec')]
            if not which:
                print('No valid selection in --which; defaulting to all')
                which = ['f1', 'fe', 'wec']
    else:
        which = interactive_menu()

    cmds = build_commands(which, args.f1_year, args.fe_season, args.wec_year, args.upload, args.dry_run, args.calendar_id, args.creds)

    for cmd in cmds:
        print('\nRunning:', ' '.join(shlex.quote(c) for c in cmd))
        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as e:
            print('Command failed:', e)


if __name__ == '__main__':
    main()
