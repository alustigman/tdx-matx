"""
Bakes the MATX library into one self-contained .tox for release (the Matx COMP's Release pulse).

The release is a Base COMP named MATX holding copies of the Matx COMP's `core`, `snippets`,
`nodes` and `fam` (the TDFam component that publishes `nodes` as the MATX family). Everything that
reads a file is baked in: every DAT synced to or loaded from a file keeps its text with the file
reference cleared, and every COMP's external .tox reference is cleared (its contents are already
loaded). The developer-only parts stay behind: `scratch`, the Build and Release pulses.

Dropping the .tox into a project gives:
  - op.Matx: the MATX COMP carries the `Matx` op shortcut every node's callbacks use;
  - the MATX family in the OP Create (TAB) menu: `fam` keeps Install and Install On Start on, so
    TDFam registers and installs it when the COMP loads.

Press Release on /matx, or run `op.Matx.op('core/td_release').module.release(op.Matx)`. It runs
Build first, then bakes a few frames later (BAKE_DELAY), once the deferred TDFam reinstall of the
build has landed. `bake` alone saves the library as it is now.

The staging copy lives for one frame only: a copied TDFam component tries to register its family at
the end of the frame it was created in, which, the family being owned by /matx/fam, would open an
"Already Registered" dialog. Copying, baking, saving and destroying in one call means the copy is
gone by then (TDFam logs that it could not reach the registry, nothing else).
"""
import datetime
import os
from typing import Optional

RELEASE_NAME = 'MATX'                        # the released COMP's name
SHIPPED = ('core', 'snippets', 'nodes', 'fam')
SHORTCUT = 'Matx'                            # op shortcut the nodes' callbacks resolve
BAKE_DELAY = 15                              # frames between Build and bake (reinstall runs at +5, +7)
DEFAULT_FILE = 'release/MATX.tox'


def release(matx_comp: COMP, path: Optional[str] = None) -> list:
	"""Builds the library from the repo files, then bakes it to `path` (the Releasefile parameter
	when None) BAKE_DELAY frames later. Returns the build's report."""
	report = matx_comp.op('core/td_builder').module.build_all(matx_comp)
	path = path or str(matx_comp.par.Releasefile.eval()) or DEFAULT_FILE
	run("op.Matx.op('core/td_release').module.bake_and_log(args[0], args[1])", matx_comp, path,
	    delayFrames=BAKE_DELAY)
	report.append('baking %s in %d frames' % (path, BAKE_DELAY))
	return report


def bake_and_log(matx_comp: COMP, path: str) -> None:
	"""bake() for a deferred run: reports to the textport and the status bar instead of returning."""
	try:
		lines = bake(matx_comp, path)
	except Exception as e:
		ui.status = 'MATX release failed: %s' % e
		debug('MATX release failed: %s' % e)
		raise
	for line in lines:
		debug(line)
	ui.status = lines[-1]


def bake(matx_comp: COMP, path: str) -> list:
	"""Saves the baked MATX COMP to `path` (relative to the project folder unless absolute) and
	returns a report whose last line names the file."""
	report = []
	abs_path = path if os.path.isabs(path) else os.path.join(project.folder, path)
	missing = [n for n in SHIPPED if matx_comp.op(n) is None]
	if missing:
		raise ValueError('%s has no %s: press Build first' % (matx_comp.path, ', '.join(missing)))
	staging = matx_comp.create(baseCOMP, 'release_staging')
	try:
		rel = staging.create(baseCOMP, RELEASE_NAME)
		rel.copyOPs([matx_comp.op(n) for n in SHIPPED])
		# saved with the release; op.Matx keeps resolving to matx_comp, its first holder, meanwhile
		rel.par.opshortcut = SHORTCUT
		_about(rel, report)
		_bake_files(rel, report)   # before the license DATs, which are text only
		_license_dats(rel)
		rel.nodeX, rel.nodeY = 0, 0
		rel.save(abs_path, createFolders=True)
	finally:
		staging.destroy()
	size = os.path.getsize(abs_path) / 1024.0
	report.append('saved %s (%.0f KB)' % (abs_path.replace('\\', '/'), size))
	return report


def _about(rel: COMP, report: list) -> None:
	"""A read-only About page on the released COMP: where and when it was built."""
	page = rel.appendCustomPage('About')
	built = page.appendStr('Built', label='Built')[0]
	built.val = '%s, %s' % (_source_version(), datetime.datetime.now().strftime('%Y-%m-%d %H:%M'))
	built.readOnly = True
	built.help = ('Source revision (git branch @ commit) and time this MATX release was baked from. '
	              'Re-bake with the Release pulse on the development /matx COMP.')
	report.append('built from %s' % built.val)


# (DAT name, repo file): tdx-matx's license, and TDFam's NOTICE, which Apache-2.0 requires to ship with
# a component that includes TDFam (fam already carries TDFam's LICENSE DAT)
LICENSE_DATS = (('LICENSE', 'LICENSE'), ('NOTICE_TDFam', 'third_party/TDFam/NOTICE'))


def _license_dats(rel: COMP) -> None:
	"""Text DATs holding the release's license and notices, in a column right of its contents."""
	x = max(c.nodeX + c.nodeWidth for c in rel.children) + 200
	x = int(-(-x // 200) * 200)
	for i, (name, rel_file) in enumerate(LICENSE_DATS):
		with open(os.path.join(project.folder, rel_file), encoding='utf-8') as f:
			text = f.read()
		d = rel.create(textDAT, name)
		d.text = text
		d.nodeX, d.nodeY = x, -i * 200


def _bake_files(rel: COMP, report: list) -> None:
	"""Clears every file reference inside rel, keeping the content it loaded."""
	dats = toxes = 0
	for o in rel.findChildren(includeUtility=True):
		if o.family == 'DAT' and o.par['file'] is not None and str(o.par.file.eval()):
			text = o.text
			for name in ('syncfile', 'loadonstart'):
				if o.par[name] is not None:
					o.par[name].val = False
			o.par.file.val = ''
			if o.text != text:   # never ship a DAT that lost its content
				raise RuntimeError('%s changed when its file was cleared' % o.path)
			dats += 1
		if o.isCOMP and str(o.par.externaltox.eval()):
			o.par.enableexternaltox.val = False
			o.par.externaltox.val = ''
			toxes += 1
		for p in o.pars():   # what is left: absolute paths only work on this machine
			if (p.style in ('File', 'Folder') and p.mode == ParMode.CONSTANT
					and os.path.isabs(str(p.eval())) and p.name not in ('file', 'externaltox')):
				report.append('WARNING: %s.%s still reads %s' % (o.path, p.name, p.eval()))
	report.append('baked %d file DATs and %d external .tox references into %s' % (dats, toxes, rel.name))


def _source_version() -> str:
	"""`branch @ short sha` of the project's git checkout, read from .git without running git."""
	git = os.path.join(project.folder, '.git')
	try:
		with open(os.path.join(git, 'HEAD'), encoding='utf-8') as f:
			head = f.read().strip()
		if not head.startswith('ref: '):
			return 'detached @ %s' % head[:7]
		ref = head[len('ref: '):]
		branch = ref[len('refs/heads/'):] if ref.startswith('refs/heads/') else ref
		ref_file = os.path.join(git, *ref.split('/'))
		if os.path.isfile(ref_file):
			with open(ref_file, encoding='utf-8') as f:
				return '%s @ %s' % (branch, f.read().strip()[:7])
		with open(os.path.join(git, 'packed-refs'), encoding='utf-8') as f:
			for line in f:
				if line.rstrip().endswith(' ' + ref):
					return '%s @ %s' % (branch, line[:7])
		return branch
	except OSError:
		return 'unknown revision'
