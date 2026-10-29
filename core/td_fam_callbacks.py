"""TDFam callbacks of the MATX family: /matx/fam's Callback DAT, set by td_builder.ensure_fam.

A node placed from the TAB menu or with PlaceOp starts with its Preview on. TDFam calls every
function here whose name starts with `on`, with an info dict.
"""


def onPlaceOp(info: dict) -> bool:
	return True   # place the operator (TDFam's template default)


def onPostPlaceOp(info: dict) -> None:
	comp = info['clone']
	if comp.par['Preview'] is None:   # Evaluate Shader has no preview
		return
	comp.par.Preview = True
	# build the preview now: a Parameter Execute does not fire in the frame its COMP was copied
	op.Matx.op('core/td_builder').module.set_preview(comp)
