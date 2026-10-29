# tdx-matx — Node-based Material Shaders for TouchDesigner

`tdx-matx` is a set of TouchDesigner components (`.tox`) that let you build **GLSL MAT** shaders by chaining nodes, much like the Blender shader editor. Each component is one node (Noise Texture, Mix, Color Ramp, Principled BSDF, ...). Instead of passing pixels or CHOP samples, the components pass a **JSON description of a shader graph** from one to the next. A final **Evaluate Shader** component reads that JSON and generates the GLSL vertex/pixel shader code for a GLSL MAT.

## Core idea

```
[Texture Coord] -> [Noise Texture] -> [Color Ramp] -> [Principled BSDF] -> [Evaluate Shader] -> GLSL MAT
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
| Input | Tex Coord, Value, RGB, XYZ |
| Texture | Noise Texture, Sampler |
| Color | Mix Color |
| Converter | Math, Vector Math, Separate XYZ, Combine XYZ, Shader To RGB |
| Shader | Principled BSDF, Emission Shader |
| Output | Evaluate Shader |

- Press **Build** on `/matx` (Matx page): besides regenerating the nodes, it loads the TDFam component into `/matx/fam` from `third_party/TDFam/TDFam_create.tox` if it is missing, points it at `/matx/nodes`, and writes each node's menu label and group into its TDFam manifest. A new snippet joins the menu on the next Build; its group comes from the snippet's `// @category` header line. When a library node is not in the family colour (a node Build just created, say), Build turns the family's **Install** toggle off and back on a few frames later, which recolours the library.
- Placing a node from the TAB menu copies the library node with the family colour (set it on `/matx/fam`, Family page), with its **Preview** on (the family's callbacks DAT, `core/td_fam_callbacks.py`, which Build sets as `/matx/fam`'s Callback DAT). Every node also has an **Edit Shader** pulse that opens its `glsl/nodes/<type>.glsl` in your external editor. Placing from Python: `op.Matx.op('fam').PlaceOp(target_comp, 'Noise')`.
- TDFam is vendored under the Apache License 2.0; its `LICENSE` and `NOTICE` are kept in `third_party/TDFam/`.

## Scope

- Target: **GLSL MAT only** (vertex + pixel shader), TouchDesigner's GLSL 3.30+ dialect, using the built-in TD functions (`TDLightingPBR`, `TDEnvLightingPBR`, `TDPerlinNoise`, `TDSimplexNoise`, `TDRGBToHSV`, `TDOutputSwizzle`, ...). Reference: <https://docs.derivative.ca/Write_a_GLSL_Material>
- Shading model, v1: **PBR** (a Principled-BSDF-like node). The architecture must allow additional shading nodes later (Diffuse, Glossy, Emission, Phong, Toon, ...), as Blender does, and mixing them (Mix Shader / Add Shader).
- Out of scope for now: GLSL TOP/POP targets, geometry shaders, node-group nesting, a custom node-editor UI (we use TD's own network editor).

## Concepts

| Concept | Meaning |
|---|---|
| **Node** | One component. Has a `type`, parameters (constant inputs), and named input/output sockets. |
| **Socket** | A named input or output of a node, with a data type: `float`, `vec2`, `vec3` (also used for colors), `vec4`, `closure`. |
| **Link** | An input value of the form `["<node_id>", "<output_name>"]` referencing another node's output. |
| **Closure** | The result of a shading node (Principled BSDF etc.): a struct holding the lit radiance and alpha, so shader nodes can be mixed and added. |
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
      "type": "PrincipledBSDF",
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
  glsl/                      shared GLSL helper library and per-node snippets
  core/                      shared Python (matx.py: graph JSON + node builder, codegen.py: graph -> GLSL) (graph merge, JSON helpers, codegen) used by all Script DATs
  examples/                  demo .toe files
  tests/                     pure-Python tests for graph merging and codegen (run outside TD)
```
