# -*- coding: utf-8 -*-
"""Checks that need no runtime (no PowerPoint, no Codex, no venv): standard library only.

Usage: python3 tests/run_tests.py
"""
import os, re, sys, json, shutil, tempfile, unittest, py_compile, glob

sys.dont_write_bytecode = True
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, 'scripts')
sys.path.insert(0, SCRIPTS)
import deckenv as E
import punct
import directions
import refs


def outline():
    return {
        'title': '测试方案。',
        'pages': [
            {'id': 'p01', 'kind': 'cover', 'title': '让新品进入搜索框。', 'subtitle': '上市方案',
             'blocks': [{'type': 'text', 'text': '我们把搜索框当成成交入口：先用高互动选题把人带到搜索，再让搜索结果页上的每一条内容都能直接承接购买。'}]},
            {'id': 'p02', 'kind': 'content', 'title': '内容翻倍，互动减半',
             'blocks': [
                 {'type': 'bullets', 'items': ['搜索词布局。', '门店承接；', '达人内容。']},
                 {'type': 'bullets', 'items': ['短要点。', '把达人内容、品牌号和门店信息统一挂到同一组搜索词之下，让用户从哪个入口进来都能看到完整路径。']},
                 {'type': 'kpis', 'items': [{'value': '+96%', 'label': '笔记量。'}]},
                 {'type': 'table', 'header': ['说法。', '互动'], 'rows': [['重要场合。', '2,572']]},
                 {'type': 'text', 'text': '第一句。第二句。'},
             ],
             'takeaway': '问题不在投入不够，而在铺量稀释了内容效率。',
             'notes': '讲稿里的句号保留。', 'layout_hint': '左右分栏。'},
        ]}


class Project:
    def __init__(self, data):
        self.dir = tempfile.mkdtemp(prefix='did_test_')
        os.makedirs(os.path.join(self.dir, E.D_WHITE))
        json.dump(data, open(os.path.join(self.dir, E.D_WHITE, 'outline.json'), 'w', encoding='utf-8'), ensure_ascii=False)
        json.dump({'name': '测试', 'suffix': 'AC_0925A'}, open(os.path.join(self.dir, 'project.json'), 'w', encoding='utf-8'))

    def outline(self):
        return E.load_outline(self.dir)

    def close(self):
        shutil.rmtree(self.dir, ignore_errors=True)


class TestPunct(unittest.TestCase):
    def setUp(self):
        self.p = Project(outline())

    def tearDown(self):
        self.p.close()

    def test_rules(self):
        changes, _, mixed = punct.run(self.p.dir)
        o = self.p.outline()
        pg1, pg2 = o['pages']
        self.assertEqual(o['title'], '测试方案')
        self.assertEqual(pg1['title'], '让新品进入搜索框')
        self.assertTrue(pg1['blocks'][0]['text'].endswith('。'))            # long description keeps it
        self.assertEqual(pg2['blocks'][0]['items'], ['搜索词布局', '门店承接', '达人内容'])
        self.assertEqual(pg2['blocks'][1]['items'][0], '短要点')
        self.assertTrue(pg2['blocks'][1]['items'][1].endswith('。'))        # 40+ characters keeps it
        self.assertEqual(pg2['blocks'][2]['items'][0]['label'], '笔记量')
        self.assertEqual(pg2['blocks'][3]['header'][0], '说法')
        self.assertEqual(pg2['blocks'][3]['rows'][0][0], '重要场合')
        self.assertEqual(pg2['blocks'][4]['text'], '第一句。第二句。')        # several sentences keep it
        self.assertEqual(pg2['takeaway'], '问题不在投入不够，而在铺量稀释了内容效率')
        self.assertEqual(pg2['notes'], '讲稿里的句号保留。')
        self.assertEqual(pg2['layout_hint'], '左右分栏。')
        self.assertEqual(mixed, ['p02/b2'])
        self.assertTrue(os.path.exists(os.path.join(self.p.dir, E.D_WHITE, '标点整理.md')))
        self.assertEqual(punct.run(self.p.dir, check=True)[1], [])

    def test_check_mode_changes_nothing(self):
        before = open(os.path.join(self.p.dir, E.D_WHITE, 'outline.json'), encoding='utf-8').read()
        _, left, _ = punct.run(self.p.dir, check=True)
        self.assertTrue(left)
        self.assertEqual(before, open(os.path.join(self.p.dir, E.D_WHITE, 'outline.json'), encoding='utf-8').read())

    def test_keep_list(self):
        E.update_project(self.p.dir, punct={'keep': ['短要点。']})
        punct.run(self.p.dir)
        self.assertEqual(self.p.outline()['pages'][1]['blocks'][1]['items'][0], '短要点。')


class TestApproval(unittest.TestCase):
    def test_signature_tracks_printed_text_only(self):
        o = outline()
        sig = E.text_signature(o)
        o['pages'][1]['layout_hint'] = '改过'
        o['pages'][1]['notes'] = '改过'
        self.assertEqual(sig, E.text_signature(o))
        o['pages'][1]['title'] = '改过的标题'
        self.assertNotEqual(sig, E.text_signature(o))

    def test_gate(self):
        p = Project(outline())
        try:
            self.assertFalse(E.whiteboard_approval(p.dir)[0])
            E.update_project(p.dir, approval={'whiteboard': {'signature': E.text_signature(p.outline()), 'time': 't'}})
            self.assertTrue(E.whiteboard_approval(p.dir)[0])
            o = p.outline(); o['pages'][0]['title'] = '新标题'
            json.dump(o, open(os.path.join(p.dir, E.D_WHITE, 'outline.json'), 'w', encoding='utf-8'), ensure_ascii=False)
            self.assertFalse(E.whiteboard_approval(p.dir)[0])
        finally:
            p.close()


def direction(i, mode, dims, source='original', refs_=None):
    return {'id': i, 'name': i, 'summary': 's', 'source': source, 'refs': refs_ or [], 'light': 'Background: #FFFFFF',
            'dark': 'Background: #000000', 'imagery': 'x', 'imagery_mode': mode, 'tone': {'cover': 'dark'},
            'dims': dict(zip(['typeface', 'palette', 'layout', 'imagery', 'texture'], dims)), '_path': '/nonexistent/%s/direction.json' % i}


class TestDirections(unittest.TestCase):
    def good(self):
        return [direction('A', 'photo', ['宋体', '深绿金', '杂志', '摄影', '纸纹']),
                direction('B', 'graphic', ['黑体', '黑白', '网格', '图形', '平面']),
                direction('C', 'illustration', ['楷体', '暖橙', '居中', '插画', '颗粒'])]

    def test_pass(self):
        errs, warns = directions.check(self.good())
        self.assertEqual(errs, [])
        self.assertTrue(warns)                       # identical background colours are reported

    def test_same_dimension_or_mode_fails(self):
        d = self.good(); d[1]['dims']['palette'] = '深绿 金'
        self.assertTrue(any('配色' in e for e in directions.check(d)[0]))
        d = self.good(); d[2]['imagery_mode'] = 'photo'
        self.assertTrue(any('配图方式' in e for e in directions.check(d)[0]))

    def test_reference_needs_existing_image(self):
        d = self.good(); d[0]['source'] = 'reference'
        self.assertTrue(any('refs 为空' in e for e in directions.check(d)[0]))
        d[0]['refs'] = ['ref/none.png']
        self.assertTrue(any('参考图不存在' in e for e in directions.check(d)[0]))

    def test_count(self):
        self.assertTrue(any('需要 3 个方向' in e for e in directions.check(self.good()[:2])[0]))


class TestRefs(unittest.TestCase):
    def test_keywords(self):
        self.assertIn('参考', refs.keyword_hits('参考/风格图.png'))
        self.assertIn('moodboard', refs.keyword_hits('Moodboard_v2/a.jpg'))
        self.assertEqual(refs.keyword_hits('video/preview.png'), [])      # 'vi' only as a whole word

    def test_skip_logo(self):
        self.assertTrue(refs.SKIP_NAME.search('brand_logo.png'))
        self.assertFalse(refs.SKIP_NAME.search('风格参考.png'))


class TestPackage(unittest.TestCase):
    def test_frontmatter(self):
        head = open(os.path.join(ROOT, 'SKILL.md'), encoding='utf-8').read().split('---')[1]
        self.assertRegex(head, r'\nname: doc-image-deck\n')
        self.assertIn('文图方案', head)

    def test_referenced_files_exist(self):
        text = open(os.path.join(ROOT, 'SKILL.md'), encoding='utf-8').read()
        for ref in set(re.findall(r'references/[^`\s）)]+\.(?:md|json)', text)):
            self.assertTrue(os.path.exists(os.path.join(ROOT, ref)), ref)

    def test_deck_commands_have_scripts(self):
        deck = open(os.path.join(SCRIPTS, 'deck'), encoding='utf-8').read()
        for script in re.findall(r'"\$S/([\w/]+\.(?:py|sh))"', deck):
            self.assertTrue(os.path.exists(os.path.join(SCRIPTS, script)), script)

    def test_python_compiles(self):
        for f in glob.glob(os.path.join(SCRIPTS, '**', '*.py'), recursive=True):
            py_compile.compile(f, doraise=True, cfile=os.path.join(tempfile.gettempdir(), 'did_pyc'))

    def test_no_client_material(self):
        names = [''.join(map(chr, cs)) for cs in ([0x68a6, 0x91d1, 0x56ed], [0x4e2d, 0x5174])]   # client names
        banned = re.compile('|'.join(names + ['/Us' + 'ers/']))                                  # and personal paths
        for f in glob.glob(os.path.join(ROOT, '**', '*'), recursive=True):
            if '/private/' in f or '/.git/' in f or '__pycache__' in f or not os.path.isfile(f) or f.endswith(('.png', '.jpg')):
                continue
            text = open(f, encoding='utf-8', errors='ignore').read()
            self.assertIsNone(banned.search(text), f)


if __name__ == '__main__':
    unittest.main(verbosity=1, warnings='ignore')
