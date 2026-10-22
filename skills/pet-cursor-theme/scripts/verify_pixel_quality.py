"""Check pixel-grid colour/alpha invariants on actual exported frames."""
from pathlib import Path
import argparse,json
from PIL import Image

parser=argparse.ArgumentParser()
parser.add_argument('output',nargs='?',type=Path,
                    default=Path(__file__).resolve().parents[1]/'output/pet-pixel-complete')
out=parser.parse_args().output.resolve()
manifest=json.loads((out/'manifest.json').read_text(encoding='utf-8'))
counts={}
for state in manifest['states']:
    colours=set()
    for k in range(state['frame_count']):
        frame=Image.open(out/f'frames/{state["id"]}-48-{k}.png')
        colours.update((r,g,b) for r,g,b,a in frame.get_flattened_data() if a)
    counts[state['id']]=len(colours)
for state in manifest['states']:
    budget=state.get('pixel_palette_colors')
    if budget is not None:
        assert counts[state['id']]<=budget,(state['id'],counts[state['id']],budget)
for path in (out/'frames').glob('*.png'):
    assert set(Image.open(path).getchannel('A').get_flattened_data())<={0,255},path
animated=[s for s in manifest['states'] if s['animated']]
assert len(animated)==17,'Every role in the complete pixel theme should now be animated'
assert all(s['unique_frame_count']>=8 and s['peak_fps']==20 for s in animated)
normal=next(s for s in animated if s['id']=='normal')
assert set(normal['ticks'])=={3},'Fur loop should run continuously without a long idle hold'
report={'palette_max_opaque_colors_at_48px':max(counts.values()),
        'palette_budgets':{s['id']:s.get('pixel_palette_colors') for s in manifest['states']},
        'all_preview_alpha_binary':True,
        'unique_animated_frames':{s['id']:s['unique_frame_count'] for s in animated},
        'action_peak_fps':{s['id']:s['peak_fps'] for s in animated},
        'all_states_animated':len(animated)==17}
(out/'pixel-quality.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report))
