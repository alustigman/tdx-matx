# TDFam (vendored)

`TDFam_create.tox` from https://github.com/dotsimulate/TDFam (`modules/release/`, commit
`fa1c8d24ed21247c3271837aa6439595eb148793`, package version 1.0.1). tdx-matx uses it to publish
its node COMPs as the MATX operator family in TouchDesigner's OP Create (TAB) menu; the builder
(`core/td_builder.py`, `ensure_fam`) loads it into `/matx/fam` when that COMP is missing.

TDFam is licensed under the Apache License, Version 2.0 (see `LICENSE`); its attribution notice is
in `NOTICE`. Built with TDFam, an open-source TouchDesigner operator-family framework created by
Lyell Hintz / dotsimulate and Dan Molnar / function.str.
