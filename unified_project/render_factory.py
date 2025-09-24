# -*- coding: utf-8 -*-
import sys, json
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, StrictUndefined

def render_layer(env, unified, layer, out_dir: Path):
    name = layer['name']
    if name == 'HYSYS_ORV':
        tpl = env.get_template('hy_config.json.j2')
        (out_dir / 'hy_config.json').write_text(tpl.render(unified=unified, layer=layer, global_mechanisms=unified.get('mechanismRelationships',[])), encoding='utf-8')
    elif name == 'HYSYS_TANK':
        tpl = env.get_template('tank_config.json.j2')
        (out_dir / 'tank_config.json').write_text(tpl.render(unified=unified, layer=layer, global_mechanisms=unified.get('mechanismRelationships',[])), encoding='utf-8')
    elif name == 'TRAFFIC':
        tpl = env.get_template('traffic_config.ini.j2')
        (out_dir / 'traffic_config.ini').write_text(tpl.render(unified=unified, layer=layer, global_mechanisms=unified.get('mechanismRelationships',[])), encoding='utf-8')
    elif name == 'OMNET_GAS':
        tpl = env.get_template('gas_omnetpp.ini.j2')
        (out_dir / 'gas_omnetpp.ini').write_text(tpl.render(unified=unified, layer=layer, global_mechanisms=unified.get('mechanismRelationships',[])), encoding='utf-8')
        tpl2 = env.get_template('gas_topology.ned.j2')
        (out_dir / 'gas_topology.ned').write_text(tpl2.render(unified=unified, layer=layer, global_mechanisms=unified.get('mechanismRelationships',[])), encoding='utf-8')

def main():
    if len(sys.argv) < 3:
        print("Usage: python render_factory.py unified_layers.json out_dir/"); return
    unified_path = Path(sys.argv[1]); out_dir = Path(sys.argv[2])
    out_dir.mkdir(parents=True, exist_ok=True)
    env = Environment(loader=FileSystemLoader(str((Path(__file__).parent / 'templates').resolve())),
                      undefined=StrictUndefined, trim_blocks=True, lstrip_blocks=True)
    unified = json.loads(unified_path.read_text(encoding='utf-8'))
    for layer in unified['layers']:
        render_layer(env, unified, layer, out_dir)
    tplx = env.get_template('exchange.xml.j2')
    (out_dir / 'exchange.xml').write_text(tplx.render(unified=unified, global_mechanisms=unified.get('mechanismRelationships',[])), encoding='utf-8')

if __name__ == '__main__':
    main()
