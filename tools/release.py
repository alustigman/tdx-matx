"""
Publishes a GitHub release of the MATX library: tags the commit, and creates the release with the
baked tox as its asset and the version's CHANGELOG.md section as its notes.

Run from a terminal at the repository root, after baking:

	1. Add a `## [x.y.z] - YYYY-MM-DD` section at the top of CHANGELOG.md, commit it on main, push.
	2. In TouchDesigner press Release on /matx (or op.Matx.op('core/td_release').module.release(op.Matx)):
	   it writes release/MATX.tox, stamped with that version and the commit.
	3. python tools/release.py --dry-run     (checks everything, changes nothing)
	   python tools/release.py               (tags vX.Y.Z, pushes the tag, creates the release)

The version is the newest CHANGELOG.md entry (the same one the bake stamps on the tox). Needs the
GitHub CLI, `gh`, signed in (`gh auth login`). Refuses to publish when the tree is dirty, the branch
is not main or not pushed, the tag exists, or the tox is older than the last commit.
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHANGELOG = os.path.join(ROOT, 'CHANGELOG.md')
TOX = os.path.join(ROOT, 'release', 'MATX.tox')
ENTRY = re.compile(r'^## \[(\d+\.\d+\.\d+[^\]]*)\][^\n]*\n', re.M)   # as core/td_release.py


class ReleaseError(Exception):
	pass


def changelog_entries(text):
	"""[(version, notes)] of a changelog, newest first: the notes run to the next entry."""
	matches = list(ENTRY.finditer(text))
	return [(m.group(1), text[m.end():matches[i + 1].start() if i + 1 < len(matches) else len(text)].strip())
	        for i, m in enumerate(matches)]


def git(*args):
	return subprocess.run(('git',) + args, cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()


def check(tox, branch, dry_run):
	"""Returns (version, notes) once everything is ready to publish; raises ReleaseError otherwise."""
	with open(CHANGELOG, encoding='utf-8') as f:
		entries = changelog_entries(f.read())
	if not entries:
		raise ReleaseError('CHANGELOG.md has no "## [x.y.z]" entry')
	version, notes = entries[0]
	if not notes:
		raise ReleaseError('the CHANGELOG.md entry for %s is empty' % version)
	tag = 'v' + version

	if git('status', '--porcelain'):
		raise ReleaseError('the working tree has uncommitted changes')
	current = git('rev-parse', '--abbrev-ref', 'HEAD')
	if current != branch:
		raise ReleaseError('on branch %s, releases are made from %s' % (current, branch))
	git('fetch', '--quiet', 'origin', branch)
	if git('rev-list', 'origin/%s..HEAD' % branch):
		raise ReleaseError('%s has commits origin does not: push it first' % branch)
	if git('rev-list', 'HEAD..origin/%s' % branch):
		raise ReleaseError('origin/%s has commits this checkout does not: pull first' % branch)
	if git('tag', '--list', tag) or git('ls-remote', '--tags', 'origin', 'refs/tags/' + tag):
		raise ReleaseError('tag %s exists: add a new CHANGELOG.md entry for the next version' % tag)

	if not os.path.isfile(tox):
		raise ReleaseError('%s does not exist: press Release on /matx in TouchDesigner' % tox)
	if os.path.getmtime(tox) < int(git('log', '-1', '--format=%ct')):
		raise ReleaseError('%s is older than the last commit: press Release on /matx again' % tox)

	if shutil.which('gh') is None:
		message = 'the GitHub CLI (gh) is not installed: https://cli.github.com, then `gh auth login`'
		if not dry_run:
			raise ReleaseError(message)
		print('warning: ' + message)
	elif subprocess.run(['gh', 'auth', 'status'], cwd=ROOT, capture_output=True).returncode != 0:
		message = 'gh is not signed in: run `gh auth login`'
		if not dry_run:
			raise ReleaseError(message)
		print('warning: ' + message)
	return version, notes


def publish(version, notes, tox, dry_run):
	tag = 'v' + version
	asset = os.path.join(os.path.dirname(tox), 'MATX-%s.tox' % tag)
	steps = [
		['git', 'tag', '-a', tag, '-m', 'MATX %s' % tag],
		['git', 'push', 'origin', tag],
		['gh', 'release', 'create', tag, asset, '--verify-tag', '--title', 'MATX %s' % tag, '--notes-file', '<notes>'],
	]
	print('release %s from %s (%s)' % (tag, git('rev-parse', '--short', 'HEAD'), os.path.relpath(tox, ROOT)))
	print('asset: %s' % os.path.relpath(asset, ROOT))
	print('notes:\n' + '\n'.join('  ' + line for line in notes.splitlines()))
	if dry_run:
		print('dry run, would run:')
		for s in steps:
			print('  ' + ' '.join(s))
		return
	shutil.copyfile(tox, asset)
	with tempfile.NamedTemporaryFile('w', suffix='.md', delete=False, encoding='utf-8') as f:
		f.write(notes + '\n')
	try:
		for s in steps:
			s = [f.name if a == '<notes>' else a for a in s]
			print('$ ' + ' '.join(s))
			subprocess.run(s, cwd=ROOT, check=True)
	finally:
		os.unlink(f.name)


def main(argv=None):
	parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
	parser.add_argument('--dry-run', action='store_true', help='check and show the steps, change nothing')
	parser.add_argument('--tox', default=TOX, help='the baked tox (default release/MATX.tox)')
	parser.add_argument('--branch', default='main', help='the branch releases are made from (default main)')
	args = parser.parse_args(argv)
	try:
		version, notes = check(args.tox, args.branch, args.dry_run)
		publish(version, notes, args.tox, args.dry_run)
	except (ReleaseError, subprocess.CalledProcessError) as e:
		print('release stopped: %s' % e, file=sys.stderr)
		return 1
	return 0


if __name__ == '__main__':
	sys.exit(main())
