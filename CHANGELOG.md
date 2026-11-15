# Changelog

All notable changes to tdx-matx are listed here, newest first. Each release on GitHub carries the
baked library, `MATX-v<version>.tox`, and the notes of its section below.

## [0.1.0] - 2026-11-15

First release: node-based material shaders for TouchDesigner. Build a GLSL MAT by wiring nodes
in the network editor, the way you would in Blender's shader editor.

### How it works

- Each node is a COMP. Nodes pass a JSON description of the shader graph to each other instead of
  pixels or samples, and **Evaluate Shader** turns it into the vertex and pixel shaders of a GLSL
  MAT, binding the TOPs, uniforms and geometry attributes the graph uses on the MAT's pages.
- Evaluate Shader is also the material output: its Surface input takes a shader, or any value,
  which is shown as emission.

### Nodes

60 nodes, most of them ports of Blender's shader nodes (same inputs, same maths), in the MATX
family of the TAB menu:

- **Input:** Tex Coord, Attribute, Vertex Color, Geometry, Camera Data, Fresnel, Layer Weight,
  Time, Value, RGB, XYZ.
- **Texture:** Noise, Voronoi, White Noise, Wave, Checker, Brick, Gradient, Magic, Shape, Sampler,
  Triplanar, Normal Map.
- **Color:** Mix Color, Invert Color, Hue Saturation, Brightness Contrast, Gamma, Posterize.
- **Converter:** Math, Vector Math, Map Range, Clamp, Mix Float, Mix Vector, Separate / Combine
  XYZ, Separate / Combine Color, RGB To BW, Blackbody, Color Ramp, Shader To RGB.
- **Vector:** Mapping, Vector Rotate, Vector Transform, Bump, Polar Coordinates, Twirl, Flipbook,
  Matcap UV.
- **Shader:** PBR, Diffuse BSDF, Glossy BSDF, Toon BSDF, Emission Shader, Transparent BSDF, Mix
  Shader, Add Shader, Evaluate Shader.

### Highlights

- **PBR through TouchDesigner's own lighting**: the PBR node matches the PBR MAT and works with the
  render's Light COMPs and Environment Light COMPs; shaders mix and add like Blender's.
- **Geometry attributes by name**: Tex Coord, Attribute, Vertex Color and Geometry read POP or SOP
  attributes (`Tex`, `Color`, `PartAge`, any custom one), so a POP network can drive a material.
- **TOPs in materials**: Sampler and Color Ramp read TOPs; Normal Map samples a normal map with the
  geometry's tangents, like the PBR MAT.
- **Animate without recompiling**: Value and RGB can be uniforms (As Uniform), and Time is one.
  Menus (a Noise type, a Math operation) are compiled in.
- **Bump quality**: Low measures the slope per 2x2 pixel block; High re-evaluates the height at
  neighbouring pixels for a smooth result on any procedural texture.
- **Blender-like editing**: sockets coloured by type, a connected input greys out its parameter
  (as does a menu that leaves it unused), a Preview toggle shows a node's output on a plane, and
  Edit Shader opens a node's GLSL snippet in your editor.
- **One self-contained `.tox`**: drop `MATX.tox` into a project and the MATX family installs in the
  TAB menu. It carries the license and TDFam's notice.

### Requirements and limits

- Tested with TouchDesigner 2025.33230. Generates GLSL MAT shaders only (no GLSL TOP or POP).
- A project holds either the development `/matx` or a released `MATX`, not both (they share the
  `Matx` shortcut and the family name).
- No node groups yet.
