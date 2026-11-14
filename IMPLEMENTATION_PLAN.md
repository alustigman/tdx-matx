# tdx-matx — Implementation Plan

See `README.md` for the project overview. This document is a living plan; items under **Open questions** need a decision.

## 0. Where we left off (2026-11-14)

**Repo:** `git@github.com:alustigman/tdx-matx.git`. Branch `main`; the node library work below was done on `feature/node-library` and merged (fast-forward) at `ca3db53`.

**Working end to end in TouchDesigner 2025.33230** (`matx-testingGround.toe`):
- `/matx` is the library (op shortcut `Matx`): `core/` (Text DATs synced to `core/*.py`), `snippets/` (synced to `glsl/`), `nodes/` (generated node COMPs + `EvaluateShader`), `fam` (TDFam, the MATX TAB menu) and `scratch/`. The **Build** pulse on `/matx` regenerates `snippets/` and `nodes/` from `glsl/nodes/*.glsl`, and upgrades every node copy in the project (details in 3b).
- `/matx_demo` is the user's test scene (a sphere shaded through `evaluate1`).
- `/matx/scratch/rig` is the **shader test bench**: a POP plane and a SOP plane (or sphere) rendered with the material of `eval1`, driven by `tests/td_bench.py` (`H.compile_all()` compiles every node type on a real GLSL MAT, `H.sheet()` renders contact sheets).
- 60 nodes in 6 groups, see section 2.
- Unit tests: `python -m unittest discover -s tests` (32 tests, pure Python, no TD needed), including one that generates every snippet through every output.

**This branch's work (2026-11-14):**
1. Geometry attributes by name (`@attrib`): TexCoord reads `Tex` by default, the Attribute node reads any POP attribute, and EvaluateShader declares them on the GLSL MAT's Attributes page (section 1.7).
2. Driven uniforms (`@uniform time = absTime.seconds`) for the Time node.
3. 46 new nodes and reworked Noise, Mix Color, Math, Principled BSDF, Emission and TexCoord (section 2), with `glsl/lib/` helpers (`view`, `lighting`, `hash`, `fbm`).
4. A connected socket greys out its parameter; generated GLSL MATs compile threaded; `@in ... [low high]` slider ranges; snippet parsing memoized for the hosts.
5. Fixes: the TDFam reinstall after a heavy build, binding of an Evaluate Shader wired in the frame it was placed, manifest placement on node copies.
6. Menu-dependent parameters (`@enable`): a parameter a menu leaves unused is greyed out, like Blender hides it (Noise W outside 1D/4D, Math B for one-input operations and C outside Multiply Add, Compare, Smooth Min/Max and Wrap, and the like on Vector Math, Voronoi, White Noise, Map Range, Mapping, Shape, Vector Rotate, Wave).
7. Socket colours from Blender (float grey, vector blue-violet, colour yellow, shader green): each In/Out DAT gets the colour of its socket kind (`codegen.socket_kind`), which the network editor shows on the COMP's connector; `@out vec3 result vector` says what an output carries when its name does not.

**Loose ends:**
- A Sampler, Color Ramp or Triplanar node without a TOP is a generation error (magenta fallback) until a TOP is set on it.
- Transparency (Transparent BSDF, Mix Shader towards nothing) needs Blending turned on by hand on the Evaluate Shader's `glsl_mat` (Common page).
- Bump measures the height's slope between neighbouring pixels (`dFdx`/`dFdy`), so hard-edged heights look blocky up close.
- Vector Transform's object space is the Geometry COMP's transform; it does not include instancing.
- Compiling a node preview happens when its viewer is drawn; `H.compile_all()` is the way to compile-check everything.

**Suggested next steps**, in order:
1. Surface GLSL MAT compile errors on EvaluateShader (read `glsl_mat_info`, report on the `pixel` DAT), so a broken snippet is visible without opening the MAT. Map graph node ids (`n<op id>`) back to COMP paths in error messages.
2. Sampler options: expose extend / filter on the Sampler node and carry them through the `samplers` table to the MAT's `sampler<i>extendu/v` and `sampler<i>filter`. A default texture for a sampler without a TOP.
3. A Blending / alpha option on EvaluateShader, so transparent closures work without opening the MAT.
4. Vertex-stage nodes (Displacement), instancing attributes, more `@uniform` inputs.

**New machine setup:** clone the repo, open `matx-testingGround.toe` in TouchDesigner with Embody installed (Envoy writes `.mcp.json`), then start Claude Code in the repo. The snippet DATs point at `glsl/...` by relative path (Build sets them). If the `core/` DATs come up empty or with errors, check their File parameter points at `core/<name>.py` relative to the project folder.

## 1. Architecture

### 1.0 MATX operator family (TDFam)
`/matx/fam` is a [TDFam](https://github.com/dotsimulate/TDFam) `TDFam_create` component (vendored in `third_party/TDFam/`, Apache-2.0, with its LICENSE and NOTICE) that publishes `/matx/nodes` as the **MATX** family in TouchDesigner's OP Create (TAB) menu. Build (`td_builder.ensure_fam`) loads it from the vendored `.tox` if missing, points its `Opcomp` at `nodes`, runs TDFam's Ensure Manifests (each library node gets a `FamManifest` child COMP), writes each node's `OpInfo` label (`_label` of the snippet type: "Noise Texture", "Principled BSDF") and group (the snippet's `// @category`; EvaluateShader is `Output`), and deploys again so the menu picks them up. Placing from the menu (or `op.Matx.op('fam').PlaceOp(target, op_type)`) copies the library node, tags it, names it `<op_name><n>` and colours it with the family colour. Known upstream noise: two TDFam updater DATs keep `syncfile` paths to `install_scripts/...` that do not exist here, so `/matx/fam` and `/sys/TDFamRegistry` show two "File not found for sync" warnings.


### 1.1 Data flow
Each node COMP has (all generated by `core/td_builder.py` from the snippet header):
- `in_<socket>` **In DATs**, one per input socket. Contents: JSON text (or empty if unconnected).
- `graph_<socket>` **Script DATs**, one per output socket, all using the shared callbacks `core/td_node_callbacks.py`.
- `out_<socket>` **Out DATs** exposing the resulting JSON on the COMP's output connectors.
- custom parameters for the node's literal inputs (e.g. Scale, Roughness, Color) and a TOP parameter per sampler.
- an **Edit Shader** pulse on the first page (Matx) that pulses Edit on the node's snippet DAT in `/matx/snippets`, opening `glsl/nodes/<type>.glsl` in the external editor (`td_builder.edit_shader`).
- Every generated `glsl_mat` (Evaluate Shader and node previews) is created with Compile Behavior `threadedprevious`: shaders compile on a background thread and the previous shader keeps rendering meanwhile, so graph edits do not stall the frame. It is set only when the MAT is created, so a user's own choice is kept.
- Nodes placed through TDFam (TAB menu or `PlaceOp`) start with Preview on: `core/td_fam_callbacks.py` (`onPostPlaceOp`) is the family's Callback DAT, and it calls `set_preview` directly because a Parameter Execute does not fire in the frame its COMP was copied. The library masters keep Preview off.
- a **Preview** toggle on the first page (Matx); a `par_exec` Parameter Execute (formerly `preview_exec`) handles it and Edit Shader. On, `td_builder.set_preview` creates a `preview` COMP inside the node: EvaluateShader's contents fed by the first output's graph, plus a Geometry COMP `geo1` holding a 1x1 plane shaded by its `glsl_mat`. The node's Operator Viewer points at `geo1` and its viewer is turned on, so the preview is an interactive geometry viewer (pan, orbit, zoom; lit by the viewer's own default lighting). Off destroys the COMP, so unpreviewed nodes cost nothing.

`onCook` of the Script DAT does:
1. Parse each connected input DAT's JSON (empty -> `{"version":1,"nodes":{}}`).
2. Merge `nodes` dicts (identical id => identical node, else error).
3. Build this node's entry: `type`, `inputs` where each socket is either a link `[upstream_id, output_name]` (if connected) or the literal from the parameter.
4. Add it under this node's stable id, set `output` to this id, write the JSON text into the Script DAT.

No node carries its own code. The shared callbacks read the node's type from its read-only `Nodetype` parameter, parse that type's snippet header from `/matx/snippets` into a spec (`matx.spec_from_snippet`), and call `matx.build_node(scriptOp, spec, out_socket)`. Editing a `.glsl` header therefore re-cooks every node of that type; re-running Build adds or removes the matching DATs and parameters.

#### Script DAT facts that constrain the design
From the [Script DAT](https://docs.derivative.ca/Script_DAT) and [scriptDAT class](https://docs.derivative.ca/ScriptDAT_Class) docs:
- **Text output:** a Script DAT is a table by default. To output JSON as plain text, set `scriptOp.textFormat = True` and then assign `scriptOp.text = ...` (assigning text while still in table mode splits it on tabs; adding rows afterwards reverts it to a table). Downstream, read it with `op.text`.
- **Newlines:** `.text` removes newlines in table cells, so emit **compact single-line JSON** (`json.dumps(g, separators=(',', ':'))`). Pretty-printing is for a debug view only. `.csv` would allow multi-line cells but isn't needed.
- **Dependencies are automatic:** any op, parameter or node the Script DAT touches during `onCook` is tracked, so reading a node's custom parameters or upstream `inputs[i].text` re-cooks the chain when they change. The dependency list resets on project restart. No manual cook triggers are needed. This also means reading unrelated ops inside `onCook` (e.g. `absTime`) would cause needless re-cooks, so core code must avoid it.
- **Inputs:** `scriptOp.inputs` lists the DATs on the Script DAT's own left connectors, so sockets can feed the Script DAT directly (named In DATs inside the COMP -> Script DAT inputs in a fixed order), or the Script can read the In DATs by name with `parent().op('in_fac')`. The second is more robust against reordering; use it.
- **Custom parameters:** created in `onSetupParameters` via `scriptOp.appendCustomPage(...)`, but node parameters are better placed on the node COMP itself (the user-facing interface) so the Script DAT stays internal. `onSetupParameters` is used only for dev-time regeneration.
- **Cook level:** default `CookLevel.AUTOMATIC` (cooks only when output is used) is right. A node that isn't connected to the final Evaluate Shader doesn't cook.
- **Errors:** raise in `onCook` -> the DAT shows an error and the chain halts visibly. Prefer writing an `{"error": ...}` field into the JSON so Evaluate Shader can report which node failed.

### 1.2 Node ids
`id = "n" + str(parent().id)` (TD's op id is unique per session and survives copy as a new id). Needs verifying across save/load and tox-copy; fallback is a UUID stored in the COMP's storage/custom par at creation.

### 1.3 Link types and implicit conversion
Sockets typed `float | vec2 | vec3 | vec4 | closure`. Evaluate Shader inserts GLSL conversions at link sites (float->vec3 splat, vec4->vec3 truncate, vec3->float luminance or `.x`, as Blender does). `closure` links only to `closure` inputs.

### 1.4 Closures and shading models
A shading node (Principled BSDF, Diffuse, Glossy, Emission, ...) is a GLSL function returning

```glsl
struct Closure { vec3 radiance; float alpha; };
```

Each shading node does its own lighting loop (e.g. `TDLightingPBR` / `TDEnvLightingPBR` for PBR) and returns the lit result, so **Mix Shader** (`mix`) and **Add Shader** (`+`) are exact and new shading models are plug-in. Trade-off: lighting is evaluated once per shading node (cost scales with number of closures). The alternative (closure = material parameters, one lighting pass at output) is cheaper but mixes parameters rather than light. See Open questions.

### 1.5 Evaluate Shader
Input: JSON DAT (`in_graph`). Contents: Script DATs `vertex` and `pixel` (shader text) and `samplers` (sampler uniform name -> TOP path), a `sampler_exec` DAT Execute that applies that table to the MAT, and `glsl_mat` using them. An Out MAT `out1` (connector label Material) exposes `glsl_mat` on the COMP's output, so the material can be wired to a Null MAT and referenced from Geometry COMPs (preview COMPs skip it).

Algorithm:
1. Parse JSON; `output` (`[node_id, socket]`) is the surface (error if missing). A closure gives radiance + alpha; any other type is shaded as emission, opaque: float `x` -> `vec4(vec3(x), 1.0)`, other types through the link conversion table (vec3 `c` -> `vec4(c, 1.0)`). There is no MaterialOutput node: EvaluateShader's `in_graph` (labelled Surface) is the material output.
2. DFS from output through links; detect cycles; topologically sort; drop unreachable nodes.
3. For each node in order, look up its snippet by `type`, collect required helper functions (deduplicated, in dependency order), and emit a call: `<out_type> n_<id>_<socket> = fn_<type>(<args>);`
4. Collect **requirements** from nodes: vertex attributes/varyings (uv, normal, position, vertex color), textures (sampler slots), uniforms (exposed parameters), and emit matching vertex-shader `out` / pixel-shader `in` declarations.
5. Assemble: `#version`-less TD preamble, helpers, node functions, `main()` ending in `oFragColor = TDOutputSwizzle(...)` (plus `TDCheckDiscard()`, `TDAlphaTest()`, `TDDither()` as needed).
6. Write DATs; set GLSL MAT parameters (pixel/vertex DAT, samplers; uniforms later).
7. Surface compile errors from the MAT's Info DAT / `errors()` in a readable form. **Not done yet.**

### 1.6 Textures and dynamic values
- The **Sampler** node (Blender's Image Texture) has a TOP parameter. Evaluate Shader gathers these into its `samplers` table and binds them on the GLSL MAT's Samplers page, one block per Sampler node (implemented, see 3b).
- Constants are baked into the shader as literals (recompile on change), unless the node's **As Uniform** toggle is on (Value, RGB): then the input is a uniform bound on the MAT's Colors page (colours) or Vectors page (anything else), so it can be animated without recompiling (see 3b).

### 1.7 Geometry attributes (POPs)

- A snippet reads a geometry attribute whose **name is chosen on the node** with `// @attrib <type> <name> = <Default> [texcoord | typed]`. The builder gives the node a Str parameter (and a `<Name>type` menu for a `typed` one), the node's graph entry carries `"attribs": {"<name>": ["<Attribute>", "<type>"]}`, and the function receives the value as a parameter after the menus.
- Codegen reads it in the vertex shader with `TDAttrib_<Name>()` and passes it through the `Vertex` block as `attr_<Name>` (one member per attribute, shared by every node that reads it). `generate()` returns `attribs`: `[name, float | float2 | float3 | float4]` rows.
- EvaluateShader's `attribs` Script DAT + `attrib_exec` DAT Execute (`td_eval_callbacks.apply_attribs`) declare them on `glsl_mat`'s **Attributes page**, which is what makes `TDAttrib_<Name>()` exist: the same mechanism as the `uniforms` table and the Colors / Vectors pages.
- Probed live on 2025.33230: a missing attribute reads 0; the declared size **must match** the geometry's attribute or the values are garbage (hence the Attribute node's type menu); `TDTexCoord(0u)` is empty for POPs.
- Texture coordinates therefore use `TDTexAttrib_<Name>(0u)` (`texcoord` flavour), which is the POP attribute for POPs and `uv[0]` for SOPs. The built-in `uv` attribute (a texture node's unconnected vector, `@attr uv`) is `Tex` read that way, so it works on both. The TexCoord node has an Attribute parameter, `Tex` by default.
- A driven uniform, `// @uniform <input> = <expression>`, is always bound as a uniform and its parameter is created running the expression: the Time node's `absTime.seconds` animates shaders without recompiling.

## 2. Node catalogue

Implemented (60). The group is the snippet's `@category`, which is also its group in the MATX TAB menu. TDFam shows at most 6 groups, so Evaluate Shader sits in Shader rather than a group of its own.

| Category | Nodes |
|---|---|
| Input | Tex Coord (uv from a named attribute, window), Attribute, Vertex Color, Geometry (position, normal, incoming, object position and normal, backfacing), Camera Data, Fresnel, Layer Weight, Time, Value, RGB, XYZ |
| Texture | Noise Texture (1D-4D; fBM, multifractal, hybrid, ridged, hetero terrain), Voronoi Texture (1D-4D; F1, F2, Smooth F1, distance to edge, n-sphere radius; 4 metrics), White Noise, Wave, Checker, Brick, Gradient, Magic, Shape (circle, rectangle, rounded rectangle, polygon), Sampler (a TOP), Triplanar (a TOP, no UVs) |
| Color | Mix Color (19 blend types), Invert Color, Hue Saturation, Brightness Contrast, Gamma, Posterize |
| Converter | Math (41 operations), Vector Math (27), Map Range, Clamp, Mix Float, Mix Vector, Separate / Combine XYZ, Separate / Combine Color (RGB, HSV, HSL), RGB To BW, Blackbody, Color Ramp (a Ramp TOP), Shader To RGB |
| Vector | Mapping, Vector Rotate, Vector Transform, Normal Map, Bump, Polar Coordinates, Twirl, Flipbook, Matcap UV |
| Shader | Principled BSDF, Diffuse BSDF, Glossy BSDF, Toon BSDF, Emission Shader, Transparent BSDF, Mix Shader, Add Shader, Evaluate Shader (the material output) |

Not done: RGB Curves / Float Curve (use Color Ramp with any lookup TOP), Displacement and other vertex-stage nodes, Light Path, Object Info, environment / sky textures, Gabor.

## 3. Phases

**Phase 0 — Spike (validate approach)**
- Hand-write one PBR GLSL MAT in TD; note the minimum required boilerplate (TDDeform, TDWorldToProj, varyings, `TDOutputSwizzle`).
- Prototype 3 node COMPs (Value, Noise, Principled BSDF) + Material Output + Evaluate Shader end to end with hardcoded snippets.
- Verify: id stability, DAT chain cook behaviour on parameter change, performance of JSON parse per hop.

**Phase 1 — Core library**
- `core/matx.py`: JSON parse/merge/validate, node builder, id handling, type conversion table.
- Snippet format and loader (see 4.2). Codegen with topo sort, dedupe, cycle detection, conversions.
- Pure-Python unit tests for merge + codegen (golden GLSL strings), run outside TD.

**Phase 2 — Minimal usable set** (done)
- Done (see section 2 for the node list).
- Evaluate Shader with GLSL MAT auto-setup and sampler binding: done. Compile-error reporting: remaining.
- Example `.toe` with a textured PBR sphere: done (`/matx_demo`).

**Phase 3 — Shader mixing and more shading models** (nodes done)
- Closure struct; Diffuse, Glossy, Toon, Emission, Transparent, Mix Shader, Add Shader: done. An unconnected closure input is an empty closure (no light, alpha 0).
- Alpha/blending handling (alpha test, OIT via `TDCheckDiscard`): the shader outputs alpha; turning Blending on is still manual.

**Phase 4 — Breadth and polish** (current phase)
- Rest of catalogue: done except the items listed under section 2. Remaining: As Uniform on more nodes (any `@in` can be marked `@uniform`), vertex-stage nodes (displacement), instancing support.
- Palette entries / consistent component styling and socket colors, docs per node, optional node-creation helper (script that generates a node COMP from a declarative spec to keep all `.tox` consistent).

## 3b. Status

**Done (written, unit tested outside TD with `python -m unittest discover -s tests`):**
- `core/matx.py`: graph parse/dump/merge, `make_node`, error propagation, TD adapter `build_node(scriptOp, NODE, out_socket)`.
- `core/codegen.py`: snippet parser, topo sort + cycle detection, type conversion, literal emission, vertex/pixel generation with only the attributes the graph needs. CLI: `python core/codegen.py graph.json out_base` writes `out_base.vert/.frag`.
- Snippets in `glsl/nodes/`: TexCoord, Value, RGB, NoiseTexture, MixColor, Sampler, PrincipledBSDF, EmissionShader, ShaderToRGB.
- `examples/noise_pbr.json` and its generated `.vert` / `.frag`.

**Conventions fixed by the code:**
- Graph `output` is `[node_id, output_socket]`; at EvaluateShader it names the surface. `world_pos` and `camera_index` are always emitted (`codegen.SURFACE_ATTRS`, fog needs them). A node with several output sockets gets one Script DAT per output socket (same nodes, different `output`).
- Colors are `vec3` in v1. Node ids must start with a letter (`n<td id>`).
- Snippet defaults are `// @in vec3 name = 0.5` (one number splats) and are used when the JSON has no literal. A default can instead name a vertex attribute (`// @in vec3 vector = uv`): the unconnected input reads `iVert.<member>`, the attribute is emitted only then, and the node COMP gets a connector but no parameter for it.
- Textures: `// @sampler sampler2D image` declares a texture per node instance; the function takes the samplers first (`matx_Sampler(sampler2D image, vec3 vector, out ...)`). The node's graph entry carries `"samplers": {"image": "<TOP path>"}`, codegen declares `uniform sampler2D sMatx_<node>_<name>;` and returns the `[uniform, TOP path]` pairs as `samplers`. A sampler without a TOP is a generation error.
- Uniforms: `// @uniform <input>` marks a non-closure `@in` that may become a uniform (Value, RGB and XYZ so far; XYZ's `vector` is spatial, so its uniform goes on the Vectors page). The builder gives such a node an `Asuniform` toggle (Inputs page). When it is on, the node's Script DAT records `"uniforms": {"<input>": ["<COMP path>", "<Par name>"]}` instead of the literal and does not read the parameter's value, so animating it never recooks the graph. A connected input stays a link. Codegen declares `uniform <type> uMatx_<node>_<input>;` and returns `[uniform, COMP path, par name, page]` rows as `uniforms`. A colour input (`codegen.is_color`: vec3/vec4 without a spatial name, the same rule that gives the node an RGB parameter) goes on the Colors page, which always feeds a `vec4` (a vec3 input passes `.rgb`); anything else goes on the Vectors page. EvaluateShader's `uniforms` table + `uniform_exec` DAT Execute (`apply_uniforms()`) size glsl_mat's `color` and `vec` sequences to them (TD keeps at least one block on each) and set each `color<i>rgb<r|g|b>` / `vec<i>value<xyzw>` to an expression `op('<path relative to the MAT>').par.<Par><component>`; an unused colour alpha stays at its constant default 1. The Colors page applies no colour-space conversion: a uniform renders identically to the literal. Verified live on 2025.33230: changing RGB1's colour with As Uniform on changes the render while the graph, pixel, vertex and uniforms DATs do not recook. Copied nodes are upgraded with `td_builder.ensure_node_contents(comp, snippet, report)`.
- Menus: `// @menu <name> <item> <item>...` (lower-case tokens, the first is the default) declares a choice that is not a socket. The builder gives the node a Menu parameter (Inputs page, item labels from `_label`), the node records `"menus": {"<name>": "<item>"}`, and codegen emits `const int MATX_<TYPE>_<NAME>_<ITEM> = <index>;` ahead of the snippet body and passes the item's constant as an `int` argument after the samplers, so the snippet `switch`es on it by name and the compiler folds the switch. Changing the menu recompiles the shader. Math (31 of Blender's operations, the fallible ones returning 0 like Blender's safe variants) is the first user; Vector Math (27 operations, vec3 A/B/C + float Scale in, Vector + Value out) the second. Every operation of both was compiled live on 2025.33230.
- A failing node writes `"error"` into the graph instead of raising; it propagates downstream and `generate` raises it.

**Reference:** the generated shaders now follow TD's own Phong/PBR MAT export (`basicPBRVert.vert`, `basicPBRFrag.frag`): `Vertex` interface block (`oVert` / `iVert`), picking guard + `TDWritePickingValues()`, `TDInstanceColor/TexCoord`, `TDUVUnwrapCoord`, `TDCheckDiscard`, `TDPixelColor`, `TDFrontFacing` normal flip, 0.08 specular level, roughness clamp, premultiplied alpha, and the output tail `TDFog` -> `TDDither` -> `TDAlphaTest` -> `TDConvertColorSpace` -> `TDOutputSwizzle` with the extra color buffers zeroed. `TDCameraIndex()` is vertex-only, so it travels as `iVert.cameraIndex` (the `camera_index` attribute, always emitted because fog needs it).

**In TouchDesigner (`matx-testingGround.toe`, verified on 2025.33230):**
- `/matx` (op shortcut `Matx`) holds the library. `core/` has Text DATs synced to `core/*.py`; `snippets/` has one Text DAT per `glsl/nodes/*.glsl` (named after its `@type`) and per `glsl/lib/*.glsl` (`lib_<name>`), synced to the files; `nodes/` has one generated node COMP per snippet plus `EvaluateShader`.
- `core/td_builder.py` generates `snippets/` and `nodes/` from the `.glsl` files. Run it with the **Build** pulse on `/matx` (Matx page). It is idempotent: it adds/removes In/Out DATs to match the headers and get-or-creates parameters, never overwriting user values or destroying parameters.
- A node COMP: read-only `Nodetype` par; one `in_<socket>` In DAT per input (`connectorder` = header order); one `graph_<socket>` Script DAT + `out_<socket>` Out DAT per output (`graph`/`out_graph` for a node without outputs); one custom parameter per non-closure input, greyed out while a wire feeds its socket or an `@enable` menu condition leaves it unused (one `enableExpr` combining both) (`float` -> Float, `vec2` -> XY, `vec3`/`vec4` -> RGB/RGBA, or XYZ/XYZW when the socket name looks spatial: vector, normal, uv, ...). All Script DATs share `core/td_node_callbacks.py`, which reads the snippet header at cook time, so editing a header re-cooks its nodes.
- `EvaluateShader`: `in_graph` -> `vertex`/`pixel` Script DATs (`core/td_eval_callbacks.py`, snippets read from `/matx/snippets`) -> `glsl_mat`. Unconnected it only warns. A third Script DAT, `samplers`, outputs the (name, top) table; the `sampler_exec` DAT Execute calls `apply_samplers()` on every table change, which sizes `glsl_mat`'s Samplers sequence to it (TD keeps at least one block, left blank) and writes each TOP as a path relative to the MAT. The DAT Execute keeps the table cooking with nothing viewing it. A declared but unbound sampler only warns ("Uniform ... is unassigned") and samples a default texture; it does not crash. Existing EvaluateShader copies are upgraded with `td_builder.ensure_evaluate_contents(comp, report)`.
- `Sampler` node (`glsl/nodes/Sampler.glsl`): `Image` TOP parameter, `vector` input defaulting to the mesh UV, `color` (vec3) and `alpha` outputs. A node's TOP parameter resolves relative to the node's parent, so a sibling TOP is just its name (`ramp1`). Passing `sampler2D` as a function argument compiles on 2025.33230.
- The builder finds a library node by name, else by its `Nodetype` (so a renamed library node is updated, not duplicated).
- `/matx_demo` rebuilds `examples/noise_pbr.json` from copied nodes and renders it on a sphere: both shaders compile and link, the vertex shader is identical to `examples/noise_pbr.vert`, the lighting matches a TD PBR MAT on the same scene, and parameter changes regenerate the shader live.
- Verified: `TDInstanceTexCoord(TDTexCoord(0u))`, `read_literal` (including RGB tuplets), automatic Script DAT dependencies on In DAT text and custom parameters, In DAT `connectorder`.
- Script DAT text output: set `textFormat = True` **before** assigning `.text`, otherwise tabs split the text into table cells.
- **TouchDesigner crashes cooking a rendered GLSL MAT whose shader DATs are empty** (three crash dumps, all in `glsl_mat` cook). EvaluateShader therefore never outputs empty source: on a missing graph or any generation error (e.g. a sampler without a TOP) it outputs `codegen.fallback()`, a flat magenta shader, and reports the error on its `vertex`/`pixel` DATs.

**Next:** see section 0, "Suggested next steps".

## 4. Key technical decisions

### 4.1 Python in each `.tox`
Shared logic is in one module referenced by every node. Options: external `.py` file loaded with a relative path; or a single `matx_core` base COMP found via global OP shortcut. Prefer a global OP shortcut + external file so `.tox` files are portable.

### 4.2 Snippet format
One `.glsl` file per node type, named after its `@type`, with one header line per item (full reference in the `core/codegen.py` docstring):

```glsl
// @type Sampler
// @sampler sampler2D image     (texture per node instance -> TOP parameter)
// @in vec3 vector = uv         (default: number(s), or a vertex attribute name)
// @out vec3 color
// @out float alpha
// @attr uv                     (attributes the body reads as iVert.<member>)
// @requires hash               (helper glsl/lib/hash.glsl, included once)
void matx_Sampler(sampler2D image, vec3 vector, out vec3 color, out float alpha) { ... }
```
Other header lines: `// @category <group>`, `// @menu <name> <item>...` (a compile-time constant, see 3b), `// @attrib <type> <name> = <Attribute> [texcoord|typed]` (a geometry attribute chosen by name, see 1.7), `// @uniform <input>` or `// @uniform <input> = <expression>`, an `@out vec3/vec4` may end with `vector` or `color` (its socket colour when the name does not tell), and an `@in` may end with `[low high]`, the slider range of its parameter. `// @enable <name>... if|unless <menu> <item>...` greys out the parameters of those @in, @menu or @attrib entries unless (or while) the menu holds one of the items; several lines on one name must all hold. It only drives the UI.

Function parameters come in header order: samplers, then menus, then attribs, then inputs, then `out` outputs. The header is the single source of truth: codegen, the node's Script DATs and the builder all read it, so there is no second declaration to keep in sync. Adding a node means adding a `.glsl` file and pressing Build.

### 4.3 Validation
Implemented inside `codegen.generate` (missing output, wrong root type, missing node or snippet, closure type mismatch, cycle, sampler without a TOP) and `matx.make_node` (a failing node writes `error` into the graph, which propagates downstream). Errors name graph node ids (`n<op id>`), not COMP paths; mapping ids back to paths for EvaluateShader's message is still open.

## 5. Decisions

1. **Closures:** lit-radiance closures (each shading node runs its own lighting; Mix/Add Shader are exact). Revisit only if cost becomes a problem.
2. **Constants:** baked into the shader as literals by default. Inputs a snippet marks `@uniform` can instead be bound as uniforms per node (the As Uniform toggle), so tweaking or animating them does not recompile.
3. **Socket width:** one In DAT per input socket; width is not a concern.
4. **Stages:** no vertex-stage *nodes* in v1 (no displacement), but Evaluate Shader still emits a **vertex shader**. It is generated from the graph's requirements: nodes declare the attributes they need (`uv`, `normal`, `position`, `tangent`, `color`, ...), and the generator adds the matching `out` varyings in the vertex shader (filled from `TDPos()`, `TDNormal()`, `TDTexCoord()`, `TDPointColor()`, with `TDDeform` / `TDWorldToProj` for position) and the matching `in` declarations in the pixel shader. Unused attributes are not emitted.
5. **TD version:** latest TouchDesigner release; no backward compatibility work.

6. **Lighting scope:** Principled BSDF supports direct lights, environment lights and shadows in v1; TD's `TDLightingPBR` / `TDEnvLightingPBR` handle these.
7. **Distribution:** everything lives in a single `.toe` for now (node COMPs inside it, no separate `.tox` files yet). Nodes should still be self-contained COMPs so they can be exported to `.tox` / a palette later. Shared Python and GLSL snippets are **the repo files themselves**: Text DATs in the `.toe` are linked to them through their File parameter (Sync to file), so the files on disk are the source of truth and are edited in an external editor.
8. **Varyings:** position and normal are passed to the pixel shader in world space.

## 7. Open questions

None at the moment.
