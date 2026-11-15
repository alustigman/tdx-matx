# tdx-matx — Node-based Material Shaders for TouchDesigner

`tdx-matx` is a set of TouchDesigner components (`.tox`) that let you build **GLSL MAT** shaders by chaining nodes, much like the Blender shader editor. Each component is one node (Noise Texture, Mix, Color Ramp, PBR, ...). Instead of passing pixels or CHOP samples, the components pass a **JSON description of a shader graph** from one to the next. A final **Evaluate Shader** component reads that JSON and generates the GLSL vertex/pixel shader code for a GLSL MAT.

## Core idea

```
[Texture Coord] -> [Noise Texture] -> [Color Ramp] -> [PBR] -> [Evaluate Shader] -> GLSL MAT
        JSON          JSON +node         JSON +node        JSON +node          JSON -> GLSL
```

- Every node COMP contains a **Script DAT** that reads the incoming JSON (via an `In DAT`), appends its own node entry, and writes the result to an `Out DAT`.
- Nodes are connected by wiring COMPs' DAT connectors; the JSON carries the graph, so the order of cooking is just the order of the network.
- The JSON is modelled on **ComfyUI's API-format workflow**: a flat dictionary of nodes keyed by id, each node having a `type` and `inputs`. An input is either a literal value or a link `[source_node_id, output_name]`.
- **Evaluate Shader** is also the material output: its **Surface** input takes a shading node (a closure) or any other value, which is shaded as emission (float `x` -> `vec4(vec3(x), 1.0)`, vec3 `c` -> `vec4(c, 1.0)`). It walks the graph backwards from the node plugged into it, topologically sorts it, and emits GLSL by concatenating per-node-type snippets. It writes the result into Text DATs wired to a GLSL MAT.

## Works with TDFam

tdx-matx works with [TDFam](https://github.com/dotsimulate/TDFam), the open-source operator-family framework by Lyell Hintz / dotsimulate and Dan Molnar / function.str. The node library is published as the **MATX** operator family, so every node appears under its own MATX tab in TouchDesigner's OP Create dialog (the TAB menu), grouped like Blender's Add menu:

| Group | Nodes |
|---|---|
| Input | Tex Coord, Attribute, Vertex Color, Geometry, Camera Data, Fresnel, Layer Weight, Time, Value, RGB, XYZ |
| Texture | Noise, Voronoi, White Noise, Wave, Checker, Brick, Gradient, Magic, Shape, Sampler, Triplanar |
| Color | Mix Color, Invert Color, Hue Saturation, Brightness Contrast, Gamma, Posterize |
| Converter | Math, Vector Math, Map Range, Clamp, Mix Float, Mix Vector, Separate / Combine XYZ, Separate / Combine Color, RGB To BW, Blackbody, Color Ramp, Shader To RGB |
| Vector | Mapping, Vector Rotate, Vector Transform, Normal Map, Bump, Polar Coordinates, Twirl, Flipbook, Matcap UV |
| Shader | PBR, Diffuse BSDF, Glossy BSDF, Toon BSDF, Emission Shader, Transparent BSDF, Mix Shader, Add Shader, Evaluate Shader |

- Press **Build** on `/matx` (Matx page): besides regenerating the nodes, it loads the TDFam component into `/matx/fam` from `third_party/TDFam/TDFam_create.tox` if it is missing, points it at `/matx/nodes`, and writes each node's menu label and group into its TDFam manifest. A new snippet joins the menu on the next Build; its group comes from the snippet's `// @category` header line. When a library node is not in the family colour (a node Build just created, say), Build turns the family's **Install** toggle off and back on a few frames later, which recolours the library.
- Placing a node from the TAB menu copies the library node with the family colour (set it on `/matx/fam`, Family page), with its **Preview** on (the family's callbacks DAT, `core/td_fam_callbacks.py`, which Build sets as `/matx/fam`'s Callback DAT). Every node also has an **Edit Shader** pulse that opens its `glsl/nodes/<type>.glsl` in your external editor. Placing from Python: `op.Matx.op('fam').PlaceOp(target_comp, 'Noise')`.
- TDFam is vendored under the Apache License 2.0; its `LICENSE` and `NOTICE` are kept in `third_party/TDFam/`.
- The PBR node is TouchDesigner's PBR MAT as a shading node (Blender's Principled BSDF plays that role there). Build renames older `PrincipledBSDF` nodes to it in place, keeping their wires and values.

## Release

Press **Release** on `/matx` (Matx page) to get one self-contained `.tox` to use in other projects. It runs Build, then a few frames later saves a Base COMP named `MATX` to **Release File** (`release/MATX.tox` by default, git-ignored). `MATX` holds copies of `core`, `snippets`, `nodes` and the TDFam `fam`, with every file baked in: each DAT that was synced to or loaded from a file keeps its text and loses the file reference, and external `.tox` references inside TDFam are cleared. It also carries the `Matx` op shortcut, this repo's `LICENSE`, TDFam's `NOTICE`, and a read-only **Built** parameter (About page) with the git branch, commit and time it was baked from. The scratch rig and the Build and Release pulses stay behind.

Drop `MATX.tox` into a project and the MATX family installs itself in the TAB menu (the family's Install and Install On Start are on). A project can hold either the development `/matx` or a released `MATX`, not both: they share the `Matx` shortcut and the MATX family name.

From Python: `op.Matx.op('core/td_release').module.release(op.Matx)`, or `bake(op.Matx, path)` to save the library as it is without building.

## Nodes

60 nodes, most of them ports of Blender's shader nodes (same inputs, same maths), plus a few from other shader graphs (Shape, Triplanar, Twirl, Flipbook, Matcap UV, Posterize, Toon BSDF) and some that only make sense in TouchDesigner (Sampler and Color Ramp read a TOP, Time is a uniform driven by `absTime.seconds`).

- **Each node is one file**, `glsl/nodes/<Type>.glsl`: a header of `// @...` lines declaring its sockets, menus and attributes, then a GLSL function. The comment above the function documents the node. Press **Edit Shader** on any node to open its file; saving it updates every node of that type.
- **Textures default to the mesh UV.** A texture node's unconnected Vector reads the geometry's texture coordinates; connect a Tex Coord, Mapping, Geometry or any vector to change that.
- **Sockets are coloured like Blender's**: grey for a float, blue-violet for a vector, yellow for a colour, green for a shader. TouchDesigner draws the colour as a band where the wire attaches and as an outline on an empty connector (it comes from the In/Out DAT behind the connector).
- **Menus are compile-time constants** (the Noise type, the Voronoi feature, a Math operation): changing one recompiles the shader, everything else is an input you can wire.
- **A connected input greys out its parameter**, the way Blender hides a socket's value field, and so does a menu that leaves it unused: Noise's W outside 1D and 4D, Math's C outside Multiply Add, Compare, Smooth Min/Max and Wrap. A snippet declares it with `// @enable c if operation multiply_add ...`.

### Geometry attributes (POPs)

Shaders read geometry attributes by name, so anything a POP network computes can drive a material:

- **Tex Coord** has an Attribute parameter, `Tex` by default: the POP texture attribute, and texture layer 0 of a SOP.
- **Attribute** reads any attribute (`Color`, `PartAge`, a custom one). Set its type to the attribute's size (Float, Vec2, Vec3, Vec4): TouchDesigner needs the exact size.
- **Vertex Color** is the point colour (`Color`), **Geometry** gives position and normal.

Evaluate Shader declares every attribute the graph reads on its GLSL MAT's **Attributes** page, the same way it fills the Samplers, Colors and Vectors pages. A missing attribute reads as 0.

## Scope

- Target: **GLSL MAT only** (vertex + pixel shader), TouchDesigner's GLSL 3.30+ dialect, using the built-in TD functions (`TDLightingPBR`, `TDEnvLightingPBR`, `TDPerlinNoise`, `TDSimplexNoise`, `TDRGBToHSV`, `TDOutputSwizzle`, ...). Reference: <https://docs.derivative.ca/Write_a_GLSL_Material>
- Shading: **PBR** through TouchDesigner's own lighting functions (PBR, the Diffuse, Glossy and Toon BSDFs, Emission, Transparent), mixed with Mix Shader / Add Shader as in Blender.
- Out of scope for now: GLSL TOP/POP targets, geometry shaders, node-group nesting, a custom node-editor UI (we use TD's own network editor).

## Concepts

| Concept | Meaning |
|---|---|
| **Node** | One component. Has a `type`, parameters (constant inputs), and named input/output sockets. |
| **Socket** | A named input or output of a node, with a data type: `float`, `vec2`, `vec3` (also used for colors), `vec4`, `closure`. |
| **Link** | An input value of the form `["<node_id>", "<output_name>"]` referencing another node's output. |
| **Closure** | The result of a shading node (PBR etc.): a struct holding the lit radiance and alpha, so shader nodes can be mixed and added. |
| **Snippet** | A GLSL function template associated with one node type, stored in the node's `.tox` (a `.glsl` file in `glsl/`, linked to a Text DAT in the .toe). |
| **Evaluate Shader** | The terminal component that turns the JSON graph into shader source. |

## JSON format (draft)

```json
{
  "version": 1,
  "nodes": {
    "n_a1": {
      "type": "TexCoord",
      "inputs": {}
    },
    "n_b2": {
      "type": "NoiseTexture",
      "inputs": {
        "vector": ["n_a1", "uv"],
        "scale": 5.0,
        "detail": 2.0
      }
    },
    "n_c3": {
      "type": "PBR",
      "inputs": {
        "base_color": ["n_b2", "color"],
        "metallic": 0.0,
        "roughness": 0.4
      }
    }
  },
  "output": ["n_c3", "bsdf"]
}
```

- `output` is the node output plugged into Evaluate Shader: it is the surface the material renders.
- Node ids are stable and unique per node COMP (derived from the COMP's TD `id`/path), so merging JSON from several upstream branches never collides.
- A node with several inputs (e.g. Mix: `fac`, `a`, `b`) has one DAT input per socket; its Script DAT merges the `nodes` dicts of all connected upstream JSONs before adding itself.
- Unconnected sockets use the literal default from the node's parameters.

## Repository layout (planned)

```
tdx-matx/
  README.md                  this file
  IMPLEMENTATION_PLAN.md     phased plan and open questions
  third_party/TDFam/         vendored TDFam (TDFam_create.tox + LICENSE + NOTICE), see "Works with TDFam"
  tdx-matx.toe               the project file; all node COMPs live inside it for now (exportable to .tox later)
  nodes/                     (later) exported .tox per node, grouped by category
  glsl/                      nodes/ (one snippet per node type) and lib/ (helpers shared through @requires: view, lighting, hash, fbm)
  core/                      shared Python (matx.py: graph JSON + node builder, codegen.py: graph -> GLSL, td_builder.py: builds the library in TD, td_release.py: bakes the release .tox) used by all Script DATs
  release/                   (git-ignored) MATX.tox written by the Release pulse, see "Release"
  examples/                  demo .toe files
  tests/                     pure-Python tests for graph merging and codegen (run outside TD); td_bench.py drives the shader test bench inside TD (/matx/scratch/rig)
```
