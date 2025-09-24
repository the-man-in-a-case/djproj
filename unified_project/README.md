# Multi-Simulator Config Factory (Unified JSON + Jinja2)

This bundle demonstrates a **factory** that converts a unified JSON into five target config files (four simulators + middleware), and a **stripper** that converts existing target files back into the unified JSON.

## Files

- `unified_project/unified_layers.json` — unified data extracted from your uploaded sample files.
- `unified_project/templates/` — Jinja2 templates for:
  - `hy_config.json.j2` (HYSYS-ORV)
  - `tank_config.json.j2` (HYSYS-Tank)
  - `traffic_config.ini.j2` (Traffic)
  - `gas_omnetpp.ini.j2` and `gas_topology.ned.j2` (OMNeT++)
  - `exchange.xml.j2` (HLA middleware)
- `unified_project/render_factory.py` — render factory CLI.
- `unified_project/stripper.py` — reverse parser CLI.

## Quick start

```bash
# 1) Render to ./out from provided unified JSON
python render_factory.py unified_layers.json ./out

# 2) Strip back from target files (any subset) into a unified JSON
python stripper.py --in ./out/hy_config.json --in ./out/tank_config.json --in ./out/traffic_config.ini --in ./out/gas_omnetpp.ini --in ./out/gas_topology.ned --in ./out/exchange.xml --out ./reunified.json
```

The templates are written so that if the unified JSON preserves the original ordering of nodes/values, the outputs will be **byte-for-byte reproducible**. For `gas_topology.ned`, the template falls back to the **original raw text** stored in `layer.metadata.ned_raw` to ensure exact reproduction when needed.
