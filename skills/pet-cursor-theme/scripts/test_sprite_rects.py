"""Regression: uneven sprite spacing must not leak a neighboring frame."""
import unittest
from pathlib import Path
from PIL import Image,ImageDraw
from build_complete_theme import prepare

class ExplicitSpriteRectTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder=Path(__file__).resolve().parents[1]/'.build-checks/sprite-tests'
        cls.folder.mkdir(parents=True,exist_ok=True)

    def test_neighbor_is_excluded_and_anchor_kept(self):
        path=self.folder/'uneven-sheet.png'
        sheet=Image.new('RGBA',(200,100))
        draw=ImageDraw.Draw(sheet)
        draw.rectangle((25,15,110,80),fill=(220,0,0,255))
        draw.rectangle((135,15,195,80),fill=(0,80,220,255))
        sheet.save(path)
        spec={'id':'regression','source':str(path),'grid':[2,1],
              'source_rects':[[0,0,120,100],[120,0,200,100]],
              'landmark_units':'pixels','landmarks':[[30,20],[20,20]]}
        frames,anchor,_=prepare(spec)
        self.assertFalse(any(r>100 and b<50 and a>0 for r,g,b,a in frames[1].get_flattened_data()),
                         'Uniform slicing leaks the red neighbor into frame 2')
        self.assertEqual(frames[0].getpixel(anchor),(220,0,0,255))
        self.assertEqual(frames[1].getpixel(anchor),(0,80,220,255))

    def test_invalid_rectangle_is_rejected(self):
        path=self.folder/'invalid-sheet.png';Image.new('RGBA',(20,20),'white').save(path)
        with self.assertRaises(ValueError):
            prepare({'id':'invalid','source':str(path),'grid':[1,1],
                     'source_rects':[[0,0,30,20]],'landmarks':[[.5,.5]]})

if __name__=='__main__':unittest.main()
