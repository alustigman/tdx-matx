"""The release script's changelog parsing, and that CHANGELOG.md has a usable newest entry."""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import release  # noqa: E402


class Release(unittest.TestCase):
	def test_entries_newest_first_with_their_notes(self):
		text = ('# Changelog\n\nIntro.\n\n## [0.2.0] - 2027-01-02\n\n- Two.\n\n'
		        '## [0.1.0] - 2026-11-15\n\n### Added\n- One.\n')
		self.assertEqual(release.changelog_entries(text),
		                 [('0.2.0', '- Two.'), ('0.1.0', '### Added\n- One.')])
		self.assertEqual(release.changelog_entries('# Changelog\n'), [])

	def test_changelog_has_a_newest_entry(self):
		with open(os.path.join(ROOT, 'CHANGELOG.md'), encoding='utf-8') as f:
			entries = release.changelog_entries(f.read())
		self.assertTrue(entries and entries[0][1], 'CHANGELOG.md needs a "## [x.y.z]" entry with notes')


if __name__ == '__main__':
	unittest.main()
