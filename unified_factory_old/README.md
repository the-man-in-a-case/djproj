
# Unified Multi-Simulator Config Factory

This toolkit does **three** things:

1. **Extract** parameters from 12 source config files (Traffic, OMNeT++ Gas INI + NED, HYSYS-ORV JSON, HYSYS-Tank JSON, OpenDSS 6 files, Middleware `exchange.xml`) into a **unified JSON** structure:
   ```json
   {
     "project": {"name": "..."},
     "layers": [{
       "name": "...",
       "simulator": "...",
       "version": "unknown",
       "metadata": {...},
       "nodes": [{"id": "...","type":"...","attrs":{...}}],
       "lines": [{"id":"...","type":"...","from":"...","to":"...","attrs":{...}}],
       "mechanismRelationships": [{...}]
     }]
   }
   ```

2. Provide **12 Jinja2 templates** to regenerate each target file from the unified JSON.

3. Provide a **renderer** to write selected or all target files.

---

## Quick Start

```bash
# 1) Make sure the original 12 files exist under /mnt/data/
# 2) Run the demo to build unified.json and render all
python main.py
```

Generated files will be under `generated_out/`. The intermediate `generated/unified.json` contains the extracted data.

---

## Selective Rendering

Use the `render_all(..., select=[...])` argument to render a subset:
```python
render_all(unified, "out_dir", "templates", select=["lines.dss","loads.dss"])
```

---

## Notes

- **Prefixes** map files to simulators; files without a prefix are the 6 OpenDSS power configs.
- The gas INI (`gas_omnetpp.ini`) and NED (`gas_topology.ned`) split **attributes** (node-level) from **edges** (GasPipe connections).
- The middleware `exchange.xml` becomes `mechanismRelationships` entries (objects/interactions).
- The templates try to mirror the original formatting while using loops/conditions for repeated sections.
