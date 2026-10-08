# tdx-matx — Node-based Material Shaders for TouchDesigner

`tdx-matx` is a set of TouchDesigner components (`.tox`) that let you build **GLSL MAT** shaders by chaining nodes, much like the Blender shader editor. Each component is one node (Noise Texture, Mix, Color Ramp, Principled BSDF, ...). Instead of passing pixels or CHOP samples, the components pass a **JSON description of a shader graph** from one to the next. A final **Evaluate Shader** component reads that JSON and generates the GLSL vertex/pixel shader code for a GLSL MAT.

## Core idea

```
[Texture Coord] -> [Noise Texture] -> [Color Ramp] -> [Principled BSDF] -> [Material Output] -> [Evaluate Shader] -> GLSL MAT
        JSON          JSON +node         JSON +node        JSON +node           JSON +node        JSON -> GLSL
```

- Every node COMP contains a **Script DAT** that reads the incoming JSON (via an `In DAT`), appends its own node entry, and writes the result to an `Out DAT`.
- Nodes are connected by wiring COMPs' DAT connectors; the JSON carries the graph, so the order of cooking is just the order of the network.
- The JSON is modelled on **ComfyUI's API-format workflow**: a flat dictionary of nodes keyed by id, each node having a `type` and `inputs`. An input is either a literal value or a link `[source_node_id, output_name]`.
- **Evaluate Shader** walks the graph backwards from the output node, topologically sorts it, and emits GLSL by concatenating per-node-type snippets. It writes the result into Text DATs wired to a GLSL MAT.

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
    },
    "n_d4": {
      "type": "MaterialOutput",
      "inputs": { "surface": ["n_c3", "bsdf"] }
    }
  },
  "output": ["n_d4", null]
}
```

- Node ids are stable and unique per node COMP (derived from the COMP's TD `id`/path), so merging JSON from several upstream branches never collides.
- A node with several inputs (e.g. Mix: `fac`, `a`, `b`) has one DAT input per socket; its Script DAT merges the `nodes` dicts of all connected upstream JSONs before adding itself.
- Unconnected sockets use the literal default from the node's parameters.

## Repository layout (planned)

```
tdx-matx/
  README.md                  this file
  IMPLEMENTATION_PLAN.md     phased plan and open questions
  scriptDat_callbacks_template.py   TD Script DAT callbacks template
  tdx-matx.toe               the project file; all node COMPs live inside it for now (exportable to .tox later)
  nodes/                     (later) exported .tox per node, grouped by category
  glsl/                      shared GLSL helper library and per-node snippets
  core/                      shared Python (matx.py: graph JSON + node builder, codegen.py: graph -> GLSL) (graph merge, JSON helpers, codegen) used by all Script DATs
  examples/                  demo .toe files
  tests/                     pure-Python tests for graph merging and codegen (run outside TD)
```
