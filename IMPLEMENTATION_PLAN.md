# tdx-matx — Implementation Plan

See `README.md` for the project overview. This document is a living plan; items under **Open questions** need a decision.

## 1. Architecture

### 1.1 Data flow
Each node COMP has:
- `in1..inN` **In DATs**, one per input socket (named after the socket). Contents: JSON text (or empty if unconnected).
- a **Script DAT** (`build_node`) with the node-specific callbacks (based on `scriptDat_callbacks_template.py`).
- an **Out DAT** exposing the resulting JSON on the COMP's output connector.
- custom parameters for the node's literal inputs (e.g. Scale, Roughness, Color).

`onCook` of the Script DAT does:
1. Parse each connected input DAT's JSON (empty -> `{"version":1,"nodes":{}}`).
2. Merge `nodes` dicts (identical id => identical node, else error).
3. Build this node's entry: `type`, `inputs` where each socket is either a link `[upstream_id, output_name]` (if connected) or the literal from the parameter.
4. Add it under this node's stable id, set `output` to this id, write the JSON text into the Script DAT.

To avoid duplicating logic in every `.tox`, node Script DATs stay tiny and call a shared module (`core/matx.py`, loaded from a Text DAT / module-on-demand or external file path) with a per-node declaration:

```python
NODE = {
  'type': 'NoiseTexture',
  'inputs':  {'vector': 'vec3', 'scale': 'float', 'detail': 'float'},
  'outputs': {'fac': 'float', 'color': 'vec4'},
}
def onCook(scriptOp):
    matx.build_node(scriptOp, NODE)
```

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
Inputs: JSON DAT. Outputs: Text DATs `vertex`, `pixel`, plus an `info` table, and a GLSL MAT preconfigured to use them.

Algorithm:
1. Parse JSON, find `output` node (`MaterialOutput`; error if missing).
2. DFS from output through links; detect cycles; topologically sort; drop unreachable nodes.
3. For each node in order, look up its snippet by `type`, collect required helper functions (deduplicated, in dependency order), and emit a call: `<out_type> n_<id>_<socket> = fn_<type>(<args>);`
4. Collect **requirements** from nodes: vertex attributes/varyings (uv, normal, position, vertex color), textures (sampler slots), uniforms (exposed parameters), and emit matching vertex-shader `out` / pixel-shader `in` declarations.
5. Assemble: `#version`-less TD preamble, helpers, node functions, `main()` ending in `oFragColor = TDOutputSwizzle(...)` (plus `TDCheckDiscard()`, `TDAlphaTest()`, `TDDither()` as needed).
6. Write DATs; set GLSL MAT parameters (pixel/vertex DAT, samplers, uniforms).
7. Surface compile errors from the MAT's Info DAT / `errors()` in a readable form.

### 1.6 Textures and dynamic values
- **Image Texture** node has a TOP reference parameter. Evaluate Shader gathers these into a manifest and assigns them to GLSL MAT sampler slots (`sTD2DInputs[i]` via Select TOPs, or the MAT's Samplers page).
- Constants are baked into the shader as literals (recompile on change). Uniform exposure via the MAT's Vectors page is a future feature, see Decisions.

## 2. Node catalogue (target)

| Category | Nodes |
|---|---|
| Input | Texture Coordinate, Geometry (position, normal, tangent), Vertex Color, Camera/View Vector, Value, RGB, Time |
| Texture | Image Texture, Noise (Perlin/Simplex via `TDPerlinNoise` / `TDSimplexNoise`), Voronoi, Checker, Gradient, Wave |
| Color | Mix Color, Color Ramp, Hue/Saturation/Value, Brightness/Contrast, Invert, Gamma, RGB Curves (later) |
| Vector | Mapping, Normal Map, Bump, Vector Math, Vector Rotate |
| Converter | Math, Map Range, Clamp, Separate/Combine XYZ & RGB, Color <-> HSV, Fresnel/Layer Weight |
| Shader | **Principled BSDF (PBR, v1)**, Diffuse, Glossy, Emission, Transparent, Mix Shader, Add Shader; later Phong, Toon |
| Output | Material Output (surface, displacement later), **Evaluate Shader** |

## 3. Phases

**Phase 0 — Spike (validate approach)**
- Hand-write one PBR GLSL MAT in TD; note the minimum required boilerplate (TDDeform, TDWorldToProj, varyings, `TDOutputSwizzle`).
- Prototype 3 node COMPs (Value, Noise, Principled BSDF) + Material Output + Evaluate Shader end to end with hardcoded snippets.
- Verify: id stability, DAT chain cook behaviour on parameter change, performance of JSON parse per hop.

**Phase 1 — Core library**
- `core/matx.py`: JSON parse/merge/validate, node builder, id handling, type conversion table.
- Snippet format and loader (see 4.2). Codegen with topo sort, dedupe, cycle detection, conversions.
- Pure-Python unit tests for merge + codegen (golden GLSL strings), run outside TD.

**Phase 2 — Minimal usable set**
- Nodes: Texture Coordinate, Value, RGB, Math, Mix Color, Noise, Image Texture, Color Ramp, Normal Map, Principled BSDF, Material Output.
- Evaluate Shader with GLSL MAT auto-setup, sampler manifest, error reporting.
- Example `.toe` with a textured PBR sphere.

**Phase 3 — Shader mixing and more shading models**
- Closure struct; Diffuse, Glossy, Emission, Transparent, Mix Shader, Add Shader.
- Alpha/blending handling (alpha test, OIT via `TDCheckDiscard`).

**Phase 4 — Breadth and polish**
- Rest of catalogue, uniform exposure toggle, vertex-stage nodes (displacement), instancing support.
- Palette entries / consistent component styling and socket colors, docs per node, optional node-creation helper (script that generates a node COMP from a declarative spec to keep all `.tox` consistent).

## 3b. Status

**Done (written, unit tested outside TD with `python -m unittest discover -s tests`):**
- `core/matx.py`: graph parse/dump/merge, `make_node`, error propagation, TD adapter `build_node(scriptOp, NODE, out_socket)`.
- `core/codegen.py`: snippet parser, topo sort + cycle detection, type conversion, literal emission, vertex/pixel generation with only the attributes the graph needs. CLI: `python core/codegen.py graph.json out_base` writes `out_base.vert/.frag`.
- Snippets in `glsl/nodes/`: TexCoord, Value, RGB, NoiseTexture, MixColor, PrincipledBSDF, MaterialOutput.
- `examples/noise_pbr.json` and its generated `.vert` / `.frag`.

**Conventions fixed by the code:**
- Graph `output` is `[node_id, output_socket]`; for MaterialOutput the socket is `null`. A node with several output sockets gets one Script DAT per output socket (same nodes, different `output`).
- Colors are `vec3` in v1. Node ids must start with a letter (`n<td id>`).
- Snippet defaults are `// @in vec3 name = 0.5` (one number splats) and are used when the JSON has no literal. A default can instead name a vertex attribute (`// @in vec3 vector = uv`): the unconnected input reads `iVert.<member>`, the attribute is emitted only then, and the node COMP gets a connector but no parameter for it.
- Textures: `// @sampler sampler2D image` declares a texture per node instance; the function takes the samplers first (`matx_Sampler(sampler2D image, vec3 vector, out ...)`). The node's graph entry carries `"samplers": {"image": "<TOP path>"}`, codegen declares `uniform sampler2D sMatx_<node>_<name>;` and returns the `[uniform, TOP path]` pairs as `samplers`. A sampler without a TOP is a generation error.
- A failing node writes `"error"` into the graph instead of raising; it propagates downstream and `generate` raises it.

**Reference:** the generated shaders now follow TD's own Phong/PBR MAT export (`basicPBRVert.vert`, `basicPBRFrag.frag`): `Vertex` interface block (`oVert` / `iVert`), picking guard + `TDWritePickingValues()`, `TDInstanceColor/TexCoord`, `TDUVUnwrapCoord`, `TDCheckDiscard`, `TDPixelColor`, `TDFrontFacing` normal flip, 0.08 specular level, roughness clamp, premultiplied alpha, and the output tail `TDFog` -> `TDDither` -> `TDAlphaTest` -> `TDConvertColorSpace` -> `TDOutputSwizzle` with the extra color buffers zeroed. `TDCameraIndex()` is vertex-only, so it travels as `iVert.cameraIndex` (the `camera_index` attribute, always emitted because fog needs it).

**In TouchDesigner (`matx-testingGround.toe`, verified on 2025.33230):**
- `/matx` (op shortcut `Matx`) holds the library. `core/` has Text DATs synced to `core/*.py`; `snippets/` has one Text DAT per `glsl/nodes/*.glsl` (named after its `@type`) and per `glsl/lib/*.glsl` (`lib_<name>`), synced to the files; `nodes/` has one generated node COMP per snippet plus `EvaluateShader`.
- `core/td_builder.py` generates `snippets/` and `nodes/` from the `.glsl` files. Run it with the **Build** pulse on `/matx` (Matx page). It is idempotent: it adds/removes In/Out DATs to match the headers and get-or-creates parameters, never overwriting user values or destroying parameters.
- A node COMP: read-only `Nodetype` par; one `in_<socket>` In DAT per input (`connectorder` = header order); one `graph_<socket>` Script DAT + `out_<socket>` Out DAT per output (`graph`/`out_graph` for MaterialOutput); one custom parameter per non-closure input (`float` -> Float, `vec2` -> XY, `vec3`/`vec4` -> RGB/RGBA, or XYZ/XYZW when the socket name looks spatial: vector, normal, uv, ...). All Script DATs share `core/td_node_callbacks.py`, which reads the snippet header at cook time, so editing a header re-cooks its nodes.
- `EvaluateShader`: `in_graph` -> `vertex`/`pixel` Script DATs (`core/td_eval_callbacks.py`, snippets read from `/matx/snippets`) -> `glsl_mat`. Unconnected it only warns. A third Script DAT, `samplers`, outputs the (name, top) table; the `sampler_exec` DAT Execute calls `apply_samplers()` on every table change, which sizes `glsl_mat`'s Samplers sequence to it (TD keeps at least one block, left blank) and writes each TOP as a path relative to the MAT. The DAT Execute keeps the table cooking with nothing viewing it. A declared but unbound sampler only warns ("Uniform ... is unassigned") and samples a default texture; it does not crash. Existing EvaluateShader copies are upgraded with `td_builder.ensure_evaluate_contents(comp, report)`.
- `Sampler` node (`glsl/nodes/Sampler.glsl`): `Image` TOP parameter, `vector` input defaulting to the mesh UV, `color` (vec3) and `alpha` outputs. A node's TOP parameter resolves relative to the node's parent, so a sibling TOP is just its name (`ramp1`). Passing `sampler2D` as a function argument compiles on 2025.33230.
- The builder finds a library node by name, else by its `Nodetype` (so a renamed library node is updated, not duplicated).
- `/matx_demo` rebuilds `examples/noise_pbr.json` from copied nodes and renders it on a sphere: both shaders compile and link, the vertex shader is identical to `examples/noise_pbr.vert`, the lighting matches a TD PBR MAT on the same scene, and parameter changes regenerate the shader live.
- Verified: `TDInstanceTexCoord(TDTexCoord(0u))`, `read_literal` (including RGB tuplets), automatic Script DAT dependencies on In DAT text and custom parameters, In DAT `connectorder`.
- Script DAT text output: set `textFormat = True` **before** assigning `.text`, otherwise tabs split the text into table cells.
- **TouchDesigner crashes cooking a rendered GLSL MAT whose shader DATs are empty** (three crash dumps, all in `glsl_mat` cook). EvaluateShader therefore never outputs empty source: on a missing graph or any generation error (e.g. the graph does not end in MaterialOutput) it outputs `codegen.fallback()`, a flat magenta shader, and reports the error on its `vertex`/`pixel` DATs.

**Next:** more nodes (Math, Color Ramp, Normal Map, Mix/Add Shader), and surfacing the GLSL MAT compile errors on the EvaluateShader COMP.

## 4. Key technical decisions

### 4.1 Python in each `.tox`
Shared logic is in one module referenced by every node. Options: external `.py` file loaded with a relative path; or a single `matx_core` base COMP found via global OP shortcut. Prefer a global OP shortcut + external file so `.tox` files are portable.

### 4.2 Snippet format
One `.glsl` file per node type with a small header, e.g.

```glsl
// @type NoiseTexture
// @in  vec3 vector, float scale, float detail
// @out float fac, vec4 color
// @requires TDPerlinNoise
void matx_NoiseTexture(vec3 vector, float scale, float detail, out float fac, out vec4 color) {
    fac = TDPerlinNoise(vector * scale) * 0.5 + 0.5;
    color = vec4(vec3(fac), 1.0);
}
```
Evaluate Shader parses headers to build calls and requirements; this keeps node authorship GLSL-first. Inputs/outputs in the header must match the node's declaration in its Script DAT (validated by a test).

### 4.3 Validation
`validate(graph)` returns errors with node ids (missing output, type mismatch, dangling link, cycle) and maps them back to COMP paths so the Evaluate component can highlight/print the offender.

## 5. Decisions

1. **Closures:** lit-radiance closures (each shading node runs its own lighting; Mix/Add Shader are exact). Revisit only if cost becomes a problem.
2. **Constants:** baked into the shader as literals in v1. Uniform exposure (no recompile on tweak) is a later feature; keep codegen behind a single `emit_value(node, socket)` function so switching a socket to a uniform later is local.
3. **Socket width:** one In DAT per input socket; width is not a concern.
4. **Stages:** no vertex-stage *nodes* in v1 (no displacement), but Evaluate Shader still emits a **vertex shader**. It is generated from the graph's requirements: nodes declare the attributes they need (`uv`, `normal`, `position`, `tangent`, `color`, ...), and the generator adds the matching `out` varyings in the vertex shader (filled from `TDPos()`, `TDNormal()`, `TDTexCoord()`, `TDPointColor()`, with `TDDeform` / `TDWorldToProj` for position) and the matching `in` declarations in the pixel shader. Unused attributes are not emitted.
5. **TD version:** latest TouchDesigner release; no backward compatibility work.

6. **Lighting scope:** Principled BSDF supports direct lights, environment lights and shadows in v1; TD's `TDLightingPBR` / `TDEnvLightingPBR` handle these.
7. **Distribution:** everything lives in a single `.toe` for now (node COMPs inside it, no separate `.tox` files yet). Nodes should still be self-contained COMPs so they can be exported to `.tox` / a palette later. Shared Python and GLSL snippets are **the repo files themselves**: Text DATs in the `.toe` are linked to them through their File parameter (Sync to file), so the files on disk are the source of truth and are edited in an external editor.
8. **Varyings:** position and normal are passed to the pixel shader in world space.

## 7. Open questions

None at the moment.
