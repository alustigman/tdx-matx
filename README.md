# tdx-matx — Node-based Material Shaders for TouchDesigner

`tdx-matx` lets you build **GLSL MAT** shaders in TouchDesigner by wiring nodes in the network editor, the way you would in Blender's shader editor. Each node (Noise Texture, Mix Color, Color Ramp, PBR, ...) is a COMP. Instead of pixels or CHOP samples, the nodes pass a **JSON description of the shader graph** to one another, and a final **Evaluate Shader** node turns it into the vertex and pixel shaders of a GLSL MAT.

```
[Tex Coord] -> [Noise Texture] -> [Color Ramp] -> [PBR] -> [Evaluate Shader] -> GLSL MAT
```

Requires TouchDesigner 2025 (tested with 2025.33230). Released under the [MIT License](LICENSE).

## Getting started

1. Download `MATX-v<version>.tox` from the [Releases page](https://github.com/alustigman/tdx-matx/releases) and drop it into your project. The MATX family installs itself in the OP Create dialog (TAB menu).
2. Place nodes from the MATX tab and wire them like Blender's nodes: a texture into a PBR's Base Color, a Math node into its Roughness, and so on.
3. Wire the last node into an **Evaluate Shader**. Its **Surface** input is the material output: it takes a shader (PBR, Mix Shader, ...) or any value, which is shown as emission.
4. Evaluate Shader's output connector is the generated material. Wire it to a Null MAT and use that as the Material of a Geometry COMP. The PBR and BSDF nodes are lit by the Render TOP's Light COMPs and Environment Light COMPs.

Each node has a **Preview** toggle that shows its output on a small plane, and an **Edit Shader** pulse that opens its GLSL in your external editor.

## Nodes

60 nodes, most of them ports of Blender's shader nodes (same inputs, same maths), plus a few from other shader graphs (Shape, Triplanar, Twirl, Flipbook, Matcap UV, Posterize, Toon BSDF) and some that only make sense in TouchDesigner (Sampler and Color Ramp read a TOP, Time is a uniform driven by `absTime.seconds`). They are grouped in the TAB menu like Blender's Add menu:

| Group | Nodes |
|---|---|
| Input | Tex Coord, Attribute, Vertex Color, Geometry, Camera Data, Fresnel, Layer Weight, Time, Value, RGB, XYZ |
| Texture | Noise, Voronoi, White Noise, Wave, Checker, Brick, Gradient, Magic, Shape, Sampler, Triplanar, Normal Map |
| Color | Mix Color, Invert Color, Hue Saturation, Brightness Contrast, Gamma, Posterize |
| Converter | Math, Vector Math, Map Range, Clamp, Mix Float, Mix Vector, Separate / Combine XYZ, Separate / Combine Color, RGB To BW, Blackbody, Color Ramp, Shader To RGB |
| Vector | Mapping, Vector Rotate, Vector Transform, Bump, Polar Coordinates, Twirl, Flipbook, Matcap UV |
| Shader | PBR, Diffuse BSDF, Glossy BSDF, Toon BSDF, Emission Shader, Transparent BSDF, Mix Shader, Add Shader, Evaluate Shader |

- **PBR is TouchDesigner's PBR MAT as a node**, the way Principled BSDF is in Blender. It uses TouchDesigner's own lighting functions, so it matches the PBR MAT. Shaders mix and add like Blender's (Mix Shader, Add Shader).
- **Textures default to the mesh UV.** A texture node's unconnected Vector reads the geometry's texture coordinates; connect a Tex Coord, Mapping, Geometry or any vector to change that.
- **Sockets are coloured like Blender's**: grey for a float, blue-violet for a vector, yellow for a colour, green for a shader.
- **A connected input greys out its parameter**, the way Blender hides a socket's value field, and so does a menu that leaves it unused (Noise's W outside 1D and 4D, Math's C outside Multiply Add, ...).
- **Menus are compiled in** (the Noise type, a Math operation): changing one recompiles the shader. Value and RGB have an **As Uniform** toggle, and Time is always a uniform, so they can be animated without recompiling.
- **TOPs in materials**: Sampler, Triplanar and Color Ramp read a TOP. Normal Map samples a tangent-space normal map with the geometry's tangents (`T`), like the PBR MAT.
- **Bump has two qualities.** Low (the default) measures the height's slope across each 2x2 block of pixels, which looks blocky up close. High evaluates the graph feeding Height twice more, at the neighbouring pixels, as Blender does: smooth everywhere, for three times the cost of that part of the graph.

### Geometry attributes (POPs)

Shaders read geometry attributes by name, so anything a POP network computes can drive a material:

- **Tex Coord** has an Attribute parameter, `Tex` by default: the POP texture attribute, and texture layer 0 of a SOP.
- **Attribute** reads any attribute (`Color`, `PartAge`, a custom one). Set its type to the attribute's size (Float, Vec2, Vec3, Vec4): TouchDesigner needs the exact size.
- **Vertex Color** is the point colour (`Color`), **Geometry** gives position and normal.

Evaluate Shader declares every attribute the graph reads on its GLSL MAT's Attributes page. A missing attribute reads as 0.

### Limits

- GLSL MAT only: no GLSL TOP or POP targets, no vertex-stage nodes (displacement), no node groups yet.
- Transparency (Transparent BSDF, a Mix Shader towards nothing) needs **Blending** turned on by hand on the Evaluate Shader's `glsl_mat` (Common page).
- A Sampler, Triplanar, Normal Map or Color Ramp without a TOP renders flat magenta until a TOP is set.
- GLSL compile errors are not reported on Evaluate Shader yet: look at its `glsl_mat_info` DAT.
- Vector Transform's object space is the Geometry COMP's transform; it does not include instancing.
- A project holds either the development `/matx` or a released `MATX`, not both: they share the `Matx` op shortcut and the MATX family name.

## How it works

Each node COMP has an In DAT per input socket and a Script DAT plus Out DAT per output socket. The Script DAT merges the JSON of everything wired into it, adds its own entry and passes the result on. Script DATs track what they read, so changing a parameter or a wire re-cooks only the chain below it.

The JSON is modelled on ComfyUI's API format: a flat dictionary of nodes keyed by a stable id (`n<op id>`), each with a `type` and `inputs`. An input is a literal or a link `[source_node_id, output_name]`, and `output` names the node plugged into Evaluate Shader (`examples/noise_pbr.json`):

```json
{
  "version": 1,
  "nodes": {
    "n_uv":    {"type": "TexCoord", "inputs": {}},
    "n_noise": {"type": "NoiseTexture", "inputs": {"vector": ["n_uv", "uv"], "scale": 4.0}},
    "n_bsdf":  {"type": "PBR", "inputs": {"base_color": ["n_noise", "color"], "roughness": 0.35}}
  },
  "output": ["n_bsdf", "bsdf"]
}
```

Nodes also carry `menus`, `samplers` (TOP paths), `uniforms` and `attribs` when they use them. A failing node writes an `error` into the graph instead of raising, and it propagates down to Evaluate Shader.

**Evaluate Shader** walks the graph back from its Surface input, sorts it topologically (and rejects cycles), and concatenates one GLSL function per node type plus the helpers they need. The vertex shader passes on only the attributes the graph reads. Links between types convert as in Blender (a float splats to a vector, a colour to a float by luminance). Evaluate Shader then binds the TOPs, uniforms and attributes on the GLSL MAT's Samplers, Colors, Vectors and Attributes pages. Generated shaders follow the structure of TouchDesigner's own PBR MAT export, and an error produces a flat magenta shader rather than an empty one (TouchDesigner crashes on a rendered GLSL MAT with empty shaders).

A shading node returns a **closure**: its lit radiance and alpha. Each shading node runs its own lighting loop, so Mix Shader and Add Shader are exact, at the cost of lighting once per shading node.

## Development

### Setup

Clone the repo and open `matx-testingGround.toe` in TouchDesigner. The project uses [Embody](https://github.com/dylanroscover/Embody) to keep its COMPs and DATs in text files, and its Envoy MCP server lets Claude Code work in the live project (see `CLAUDE.md`).

- `/matx` (op shortcut `Matx`) is the library. It holds `core/` (Text DATs synced to `core/*.py`), `snippets/` (synced to `glsl/`), `nodes/` (the generated node COMPs and `EvaluateShader`), `fam` (TDFam, the MATX TAB menu) and `scratch/` (the shader test bench).
- `/matx_demo` is a test scene.
- The repo files are the source of truth: edit them in your editor and TouchDesigner reloads them.

### Adding or changing a node

Each node is one file, `glsl/nodes/<Type>.glsl`: a header of `// @...` lines declaring its sockets, menus, samplers and attributes, then a GLSL function `matx_<Type>(...)`. The comment above the function documents the node. For example:

```glsl
// @type Sampler
// @category Texture
// @sampler sampler2D image     (a TOP parameter on the node)
// @in vec3 vector = uv         (unconnected: reads the mesh UV)
// @out vec3 color
// @out float alpha
void matx_Sampler(sampler2D image, vec3 vector, out vec3 color, out float alpha) { ... }
```

The header is the only declaration: codegen, the node's Script DATs and the builder all read it. The full list of header lines (`@menu`, `@uniform`, `@attrib`, `@enable`, `@differentiate`, `@requires`, ...) is in the docstring of `core/codegen.py`. Shared helpers live in `glsl/lib/` (`view`, `lighting`, `hash`, `fbm`) and are pulled in with `// @requires <name>`.

Press **Build** on `/matx` (Matx page) after adding a file. Build generates `snippets/` and `nodes/`, upgrades every copy of a node in the project, and writes each node's menu label and group into the TDFam family. It only adds or updates DATs and parameters, so it never overwrites values you set. Editing an existing snippet needs no Build: every node of that type re-cooks.

### Tests

- `python -m unittest discover -s tests` runs the pure-Python tests (no TouchDesigner needed), including one that generates every snippet through every output.
- `python core/codegen.py examples/noise_pbr.json out` writes the shaders for a graph to `out.vert` and `out.frag`.
- Inside TouchDesigner, `tests/td_bench.py` drives the test bench at `/matx/scratch/rig`. `op.Matx.op('scratch/rig/harness').module.compile_all()` compiles every node type on a real GLSL MAT and returns `{}` when all of them compile.

### Release

Press **Release** on `/matx` to get one self-contained `.tox` to use in other projects. It runs Build, then a few frames later saves a Base COMP named `MATX` to **Release File** (`release/MATX.tox` by default, git-ignored).

`MATX` holds copies of `core`, `snippets`, `nodes` and the TDFam `fam`, with every file baked in. It also carries:

- the `Matx` op shortcut;
- this repo's `LICENSE` and TDFam's `NOTICE`;
- an About page showing the **Version** (the newest entry of [CHANGELOG.md](CHANGELOG.md)) and **Built** (the git branch, commit and time it was baked from).

The scratch rig and the Build and Release pulses stay behind. From Python: `op.Matx.op('core/td_release').module.release(op.Matx)`, or `bake(op.Matx, path)` to save the library as it is without building.

To publish a release on GitHub (this needs the [GitHub CLI](https://cli.github.com), signed in with `gh auth login`):

1. Add a `## [x.y.z] - YYYY-MM-DD` section at the top of `CHANGELOG.md`, then commit and push it on `main`.
2. Press **Release** on `/matx`.
3. Run `python tools/release.py --dry-run` to check everything without changing anything. Then run `python tools/release.py`: it tags `vX.Y.Z`, pushes the tag, and creates the release with `MATX-vX.Y.Z.tox` and the changelog section as its notes.

The script stops if the tree is dirty, `main` isn't pushed, the tag already exists, or the tox is older than the last commit.

## Repository layout

```
tdx-matx/
  matx-testingGround.toe   the project: the /matx library, the /matx_demo scene, the test bench
  glsl/nodes/              one snippet per node type
  glsl/lib/                helpers shared through @requires (view, lighting, hash, fbm)
  core/                    shared Python: matx.py (graph JSON, node builder), codegen.py (graph -> GLSL),
                           td_builder.py (Build), td_release.py (Release), td_*_callbacks.py (DAT callbacks)
  tests/                   unit tests, and td_bench.py for the test bench inside TouchDesigner
  tools/release.py         publishes a GitHub release
  examples/                an example graph and its generated shaders
  third_party/TDFam/       vendored TDFam (Apache-2.0, with its LICENSE and NOTICE)
  release/                 (git-ignored) the baked MATX.tox
  CHANGELOG.md             release notes, newest first
```

## Credits

The MATX TAB menu is built on [TDFam](https://github.com/dotsimulate/TDFam), the open-source operator-family framework by Lyell Hintz / dotsimulate and Dan Molnar / function.str, vendored under the Apache License 2.0. Most nodes are ports of [Blender](https://www.blender.org)'s shader nodes.
