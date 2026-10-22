"""Regression checks for external-project coat variant registration."""
from pathlib import Path
import sys
import uuid
from contextlib import contextmanager
import shutil
import json
import subprocess
import unittest
from PIL import Image,ImageDraw

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import register_coat_variant as module

@contextmanager
def temporary_project(parent):
    path=parent/uuid.uuid4().hex
    assert path.resolve().is_relative_to(ROOT.resolve())
    path.mkdir()
    try:yield path
    finally:
        assert path.resolve().is_relative_to(parent.resolve())
        shutil.rmtree(path)


class RegistrationTests(unittest.TestCase):
    def make_cell(self,size=80,offset=(0,0)):
        im=Image.new('RGBA',(size,size));d=ImageDraw.Draw(im)
        x,y=offset;d.rectangle((20+x,20+y,58+x,65+y),fill='#352a22')
        d.rectangle((8+x,26+y,28+x,38+y),fill='#171717')
        d.rectangle((34+x,30+y,38+x,36+y),fill='#faf4e8')
        return im

    def test_translation_maps_reviewed_hotspot(self):
        old=self.make_cell();new=self.make_cell(offset=(5,-3))
        point,qa=module.register(old,new,1,[9,30],128)
        self.assertEqual(point,[14,27]);self.assertEqual(qa['translation'],[5,-3])
        self.assertEqual(qa['iou'],1);self.assertTrue(qa['opaque'])

    def test_alpha_registration_ignores_changed_coat_rgb(self):
        old=self.make_cell();new=self.make_cell(offset=(-4,2))
        new.paste('#c68c42',(16,22,54,60),new.crop((16,22,54,60)).getchannel('A'))
        point,qa=module.register(old,new,1,[9,30],128)
        self.assertEqual(point,[5,32]);self.assertGreater(qa['iou'],.99)

    def test_external_cli_does_not_select_old_rectangles_twice(self):
        test_root=Path(__file__).resolve().parent/'.registration-tests'
        assert test_root.resolve().is_relative_to(ROOT.resolve())
        test_root.mkdir(exist_ok=True)
        with temporary_project(test_root) as temp:
            root=Path(temp);(root/'art').mkdir();(root/'edited').mkdir()
            old=Image.new('RGBA',(160,160));new=Image.new('RGBA',(160,160))
            for i in range(4):
                old.paste(self.make_cell(),(i%2*80,i//2*80))
                new.paste(self.make_cell(offset=(3,2)),(i%2*80,i//2*80))
            old.save(root/'art/base.png');new.save(root/'edited/normal.png')
            rects=[[0,0,80,80],[0,80,80,160],[80,80,160,160]]
            cfg={'pixel_art':True,'native_pixel_size':48,'pixel_alpha_threshold':128,
                 'states':[{'id':'normal','role':'Arrow','label':'normal','idea':'test',
                 'source':'art/base.png','grid':[2,2],'source_frames':[0,2,3],
                 'source_rects':rects,'landmark_units':'pixels','landmarks':[[9,30]]*3,
                 'sequence':[0,2,1],'ticks':[3,4,8]}]}
            (root/'config.json').write_text(json.dumps(cfg),encoding='utf-8')
            (root/'edited/calibration.json').write_text(json.dumps({'normal':{
                'hotspot_overrides':{'32':[3,4]}}}),encoding='utf-8')
            result=subprocess.run([sys.executable,str(ROOT/'scripts/register_coat_variant.py'),
                '--base-config',str(root/'config.json'),'--assets-dir',str(root/'edited'),
                '--root',str(root),'--name','External'],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            data=json.loads((root/'edited/theme-config.json').read_text(encoding='utf-8'))
            state=data['states'][0]
            self.assertEqual(state['source_frames'],[0,2,3]);self.assertEqual(len(state['landmarks']),3)
            self.assertEqual(state['sequence'],[0,2,1]);self.assertEqual(state['ticks'],[3,4,8])
            self.assertEqual(state['source'],'edited/normal.png')
            self.assertEqual(state['hotspot_overrides'],{'32':[3,4]})
            qa=json.loads((root/'edited/registration-diagnostics.json').read_text(encoding='utf-8'))
            scales={f['scale'] for f in qa['states']['normal']['frames']}
            self.assertEqual(len(scales),1)


if __name__=='__main__':unittest.main()
