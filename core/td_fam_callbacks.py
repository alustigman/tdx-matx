"""TDFam callbacks of the MATX family: /matx/fam's Callback DAT, set by td_builder.ensure_fam.

A node placed from the TAB menu or with PlaceOp starts with its Preview on, and a placed Evaluate
Shader binds its GLSL MAT once more a frame later. TDFam calls every function here whose name
starts with `on`, with an info dict.
"""


def onPlaceOp(info: dict) -> bool:
	return True   # place the operator (TDFam's template default)


def onPostPlaceOp(info: dict) -> None:
	comp = info['clone']
	if comp.par['Preview'] is None:   # Evaluate Shader has no preview
		if comp.op('glsl_mat') is not None and comp.op('attribs') is not None:
			# its DAT Executes miss table changes made in the frame it was created (a script that
			# places and wires it at once), so bind again once that frame is over
			run("op.Matx.op('core/td_builder').module.bind_evaluate(args[0]) if args[0].valid else None",
			    comp, delayFrames=1)
		return
	comp.par.Preview = True
	# build the preview now: a Parameter Execute does not fire in the frame its COMP was copied
	op.Matx.op('core/td_builder').module.set_preview(comp)
