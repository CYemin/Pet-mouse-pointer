from pathlib import Path
from zipfile import ZipFile
import json, sys
from PIL import Image
sys.path.insert(0,str(Path(__file__).parent/'scripts'))
from build_samples import cur_file, ani_file
root=Path(__file__).parent
for pack in (root/'frames').glob('*.zip'):
    with ZipFile(pack) as z: z.extractall(root/'output')
for path in (root/'output').glob('*/manifest.json'):
    m=json.loads(path.read_text(encoding='utf-8')); theme=path.parent
    for s in m['states']:
        for n,rel in s['variants'].items():
            frames=[cur_file([(Image.open(theme/f"frames/{s['id']}-{n}-{i}.png").convert('RGBA'),s['hotspots'][n])]) for i in range(s['frame_count'])]
            data=ani_file(frames,s['sequence'],s['ticks']); (theme/rel).parent.mkdir(parents=True,exist_ok=True); (theme/rel).write_bytes(data)
            if n=='48': (theme/s['file']).write_bytes(data)
print('Rebuilt 24 themes, 17 states, five sizes in output/')
