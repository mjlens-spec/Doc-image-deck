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
import humanize
import hostos
import visual
import build_prompts
import brand


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
    return {'id': i, 'name': i, 'summary': 's', 'source': source, 'refs': refs_ or [], 'brand_fit': '品牌蓝作强调色',
            'light': 'Background: #FFFFFF',
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

    def test_brand_fit_required(self):
        d = self.good(); d[1]['brand_fit'] = ''
        self.assertTrue(any('brand_fit' in e for e in directions.check(d)[0]))


BRAND_DONE = """# 品牌调研

## 一、资料来源

- 01_设计方向/品牌材料/品牌手册.pdf 第 3、8 页：标准色与 Logo 组合
- https://example.com/about（2026-09-25）

## 二、品牌色

主色 #0E2A47（品牌手册第 3 页），强调色 #00B4D8

## 三、Logo

彩色版用于浅底，反白版用于深底，文件在 01_设计方向/品牌材料/

## 四、字体与版式

标题用粗黑体，正文常规黑体，物料大量留白

## 五、视觉风格与禁忌

不适用：客户没有提供品牌手册中的禁用规范，官网也没有公开

## 六、对三个方向的约束

强调色只用 #00B4D8；Logo 周围留出一个字高的空白
"""


class TestBrand(unittest.TestCase):
    def setUp(self):
        self.p = Project(outline())

    def tearDown(self):
        self.p.close()

    def write(self, text):
        os.makedirs(os.path.join(self.p.dir, E.D_DIRS), exist_ok=True)
        open(brand.path(self.p.dir), 'w', encoding='utf-8').write(text)

    def test_missing_and_template(self):
        self.assertTrue(any('还没有品牌调研' in e for e in brand.check(self.p.dir)))
        self.write(brand.template(self.p.dir))
        errs = brand.check(self.p.dir)
        self.assertEqual(len(errs), 6)                                    # every section still holds only its hint

    def test_complete(self):
        self.write(BRAND_DONE)
        self.assertEqual(brand.check(self.p.dir), [])

    def test_colour_and_source_rules(self):
        self.write(BRAND_DONE.replace('#0E2A47', '深蓝').replace('#00B4D8', '青色'))
        self.assertTrue(any('色值' in e for e in brand.check(self.p.dir)))
        self.write(BRAND_DONE.replace('不适用：客户没有提供品牌手册中的禁用规范，官网也没有公开', '不适用'))
        self.assertTrue(any('没有写理由' in e for e in brand.check(self.p.dir)))

    def test_materials(self):
        d = os.path.join(self.p.dir, E.D_DIRS, brand.MAT_DIR)
        os.makedirs(os.path.join(d, '导出'))
        open(os.path.join(d, 'vi.pdf'), 'w').close()
        open(os.path.join(d, '导出', 'vi-1.png'), 'w').close()                # exported pages are not materials
        E.update_project(self.p.dir, brand_materials=['../shot.png'])
        names = [os.path.basename(m) for m in brand.materials(self.p.dir)]
        self.assertEqual(names, ['vi.pdf', 'shot.png'])


class TestLogo(unittest.TestCase):
    def setUp(self):
        try:
            from PIL import Image  # noqa: F401
        except ImportError:
            self.skipTest('Pillow not installed')
        import logo
        self.logo = logo
        self.d = tempfile.mkdtemp(prefix='did_logo_')

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def img(self, name, ink, bg=None, size=(200, 80), dot=None):
        from PIL import Image, ImageDraw
        im = Image.new('RGBA', size, bg or (0, 0, 0, 0))
        dr = ImageDraw.Draw(im)
        dr.rectangle((20, 20, size[0] - 20, size[1] - 20), fill=ink)
        if dot:
            dr.ellipse((25, 25, 45, 45), fill=dot)
        p = os.path.join(self.d, name); im.save(p)
        return p

    def test_white_logo_gets_a_light_background_version(self):
        p = self.img('w.png', (255, 255, 255, 255), dot=(230, 180, 20, 255))
        lt, dk, note = self.logo.versions(p, self.d, (101, 101, 101))
        self.assertIn('反白', note)
        self.assertEqual(lt.getpixel((lt.width // 2, lt.height - 5))[:3], (101, 101, 101))
        self.assertEqual(lt.getpixel((12, 12))[:3], (230, 180, 20))            # coloured dot kept
        self.assertEqual(dk.getpixel((dk.width // 2, dk.height - 5))[:3], (255, 255, 255))

    def test_opaque_white_background_removed_and_pair(self):
        a = self.img('a.png', (40, 40, 40, 255), bg=(255, 255, 255, 255))
        b = self.img('b.png', (255, 255, 255, 255))
        lt, dk, note = self.logo.versions('a.png::b.png', self.d, (101, 101, 101))
        self.assertEqual(lt.size, (161, 41))                                  # trimmed to the ink
        self.assertIn('两个版本', note)

    def test_lockup_balances_area(self):
        from PIL import Image
        wide = Image.new('RGBA', (300, 100), (0, 0, 0, 255))
        tall = Image.new('RGBA', (120, 120), (0, 0, 0, 255))
        out = self.logo.lockup([tall, wide], (160, 160, 160), height=200)
        self.assertEqual(out.height, 200 // 1)
        self.assertGreater(out.width, 400)


class TestRefs(unittest.TestCase):
    def test_keywords(self):
        self.assertIn('参考', refs.keyword_hits('参考/风格图.png'))
        self.assertIn('moodboard', refs.keyword_hits('Moodboard_v2/a.jpg'))
        self.assertEqual(refs.keyword_hits('video/preview.png'), [])      # 'vi' only as a whole word

    def test_skip_logo(self):
        self.assertTrue(refs.SKIP_NAME.search('brand_logo.png'))
        self.assertFalse(refs.SKIP_NAME.search('风格参考.png'))


class TestHumanize(unittest.TestCase):
    def setUp(self):
        self.p = Project(outline())
        os.environ['DOC_IMAGE_DECK_HUMANIZER'] = os.path.join(self.p.dir, 'none')   # do not depend on the machine

    def tearDown(self):
        self.p.close()

    def roundtrip(self, edit):
        humanize.cmd_export(self.p.dir, False)
        wd = os.path.join(self.p.dir, E.D_WHITE)
        src = open(os.path.join(wd, humanize.SRC_MD), encoding='utf-8').read()
        open(os.path.join(wd, humanize.OUT_MD), 'w', encoding='utf-8').write(edit(src))

    def test_gate_and_import(self):
        self.assertTrue(humanize.pending(self.p.dir))
        self.roundtrip(lambda s: s.replace('问题不在投入不够，而在铺量稀释了内容效率。', '投入并不少，是铺量稀释了内容效率。'))
        humanize.cmd_import(self.p.dir, False)
        self.assertEqual(self.p.outline()['pages'][1]['takeaway'], '投入并不少，是铺量稀释了内容效率。')
        self.assertEqual(humanize.pending(self.p.dir), [])
        punct.run(self.p.dir)                                    # punctuation after import keeps the step done
        self.assertEqual(humanize.pending(self.p.dir), [])

    def test_fact_lock(self):
        self.roundtrip(lambda s: s.replace('+96%', '+90%').replace('笔记量。', '笔记数。'))
        # kpi values hold no Chinese and are not exported; change a number inside a Chinese string instead
        self.roundtrip(lambda s: s.replace('粉丝不足 1,000', '粉丝不足 2,000') if '1,000' in s else s.replace('让新品进入搜索框。', '让新品 2 周进入搜索框。'))
        with self.assertRaises(SystemExit):
            humanize.cmd_import(self.p.dir, False)

    def test_markers_must_match(self):
        self.roundtrip(lambda s: re.sub(r'\n⟦p02\.02[^\n]*', '', s, count=1))
        with self.assertRaises(SystemExit):
            humanize.cmd_import(self.p.dir, False)

    def test_changed_only_and_accept(self):
        self.roundtrip(lambda s: s)
        humanize.cmd_import(self.p.dir, False)
        o = self.p.outline(); o['pages'][0]['title'] = '新标题'
        json.dump(o, open(os.path.join(self.p.dir, E.D_WHITE, 'outline.json'), 'w', encoding='utf-8'), ensure_ascii=False)
        self.assertEqual([t[3] for t in humanize.pending(self.p.dir)], ['新标题'])
        humanize.cmd_accept(self.p.dir, '用户原话')
        self.assertEqual(humanize.pending(self.p.dir), [])

    def test_parse_multiline(self):
        md = '# x\n\n## p01\n⟦p01.01 标题⟧ 甲\n⟦p01.02 讲稿⟧ 第一段\n第二段\n\n## p02\n⟦p02.01 标题⟧ 乙\n'
        self.assertEqual(humanize.parse(md), {'p01.01': '甲', 'p01.02': '第一段\n第二段', 'p02.01': '乙'})


def planned(n_content, skeletons, structures=None):
    """Cover + n_content content pages + closing, each with a visual brief."""
    structures = structures or ['flow'] * n_content
    pages = [{'id': 'p01', 'kind': 'cover', 'title': '封面',
              'visual': {'message': 'm', 'structure': 'claim', 'form': 'f0', 'focal': 'x', 'skeleton': 'hero'}}]
    for i in range(n_content):
        pages.append({'id': 'p%02d' % (i + 2), 'kind': 'content', 'title': '内容 %d' % i,
                      'blocks': [{'type': 'bullets', 'items': ['甲', '乙'], 'visual': '两个节点'}],
                      'visual': {'message': 'm', 'structure': structures[i], 'form': 'f%d' % (i + 1), 'focal': 'x',
                                 'skeleton': skeletons[i]}})
    pages.append({'id': 'p%02d' % (n_content + 2), 'kind': 'closing', 'title': '封底',
                  'visual': {'message': 'm', 'structure': 'claim', 'form': 'fz', 'focal': 'x', 'skeleton': 'hero'}})
    return {'title': 't', 'pages': pages}


class TestVisual(unittest.TestCase):
    def test_pass(self):
        errs, warns = visual.check(planned(4, ['split', 'diagram', 'cards', 'bignum'], ['flow', 'loop', 'roles', 'kpi']))
        self.assertEqual(errs, [])
        self.assertEqual(warns, [])

    def test_missing_brief(self):
        o = planned(2, ['split', 'diagram'])
        del o['pages'][1]['visual']
        o['pages'][2]['visual'].pop('focal')
        errs = visual.check(o)[0]
        self.assertTrue(any('p02 没有视觉规划' in e for e in errs))
        self.assertTrue(any('p03 的视觉规划缺少：视觉焦点' in e for e in errs))

    def test_unknown_values(self):
        o = planned(2, ['split', 'grid'], ['flow', 'story'])
        errs = visual.check(o)[0]
        self.assertTrue(any('skeleton「grid」' in e for e in errs))
        self.assertTrue(any('structure「story」' in e for e in errs))

    def test_neighbours_and_overuse(self):
        errs = visual.check(planned(3, ['split', 'split', 'diagram']))[0]
        self.assertTrue(any('p02 与 p03 相邻' in e for e in errs))
        errs = visual.check(planned(2, ['split', 'hero']))[0]
        self.assertTrue(any('p03 与 p04 相邻' in e for e in errs))          # last content page vs the closing page
        errs = visual.check(planned(8, ['cards', 'split'] * 4))[0]          # 8 content pages: at most 2 per skeleton
        self.assertTrue(any('「并列卡片」用了 4 页' in e and '最多 2 页' in e for e in errs))
        warns = visual.check(planned(2, ['split', 'diagram'], ['flow', 'flow']))[1]
        self.assertTrue(any('信息结构相同' in w for w in warns))

    def test_repeated_motif(self):
        o = planned(3, ['split', 'diagram', 'bignum'], ['flow', 'loop', 'kpi'])
        for pg, m in zip(o['pages'][1:4], ['枕头切面', '枕头切面', '无照片']):
            pg['visual']['motif'] = m
        o['pages'][4]['visual']['motif'] = '无照片，纯排版'
        warns = visual.check(o)[1]
        self.assertEqual([w for w in warns if '配图母题' in w], ['p02 与 p03 的配图母题相同'])

    def test_list_fallback_is_capped(self):
        errs = visual.check(planned(4, ['split', 'diagram', 'cards', 'bignum'], ['list', 'list', 'flow', 'kpi']))[0]
        self.assertTrue(any('并列要点' in e for e in errs))

    def test_project_limits(self):
        o = planned(2, ['split', 'diagram'])
        o['pages'][2]['kind'] = 'section'
        errs = visual.check(o, {'max_pages': 3, 'section_pages': False})[0]
        self.assertTrue(any('max_pages' in e for e in errs))
        self.assertTrue(any('章节页' in e for e in errs))

    def test_relative_logo_paths(self):
        d = tempfile.mkdtemp(prefix='did_logo_')
        try:
            json.dump({'logos': [{'light': 'logo/l.png', 'dark': '/abs/d.png'}]}, open(os.path.join(d, 'project.json'), 'w'))
            lg = E.load_project(d)['logos'][0]
            self.assertEqual(lg['light'], os.path.join(d, 'logo', 'l.png'))
            self.assertEqual(lg['dark'], '/abs/d.png')
            E.update_project(d, note='x')                                   # saving keeps the relative path
            self.assertEqual(json.load(open(os.path.join(d, 'project.json')))['logos'][0]['light'], 'logo/l.png')
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_brief_does_not_touch_approval(self):
        o = planned(2, ['split', 'diagram'])
        sig = E.text_signature(o)
        o['pages'][1]['visual']['form'] = '改过'
        o['pages'][1]['blocks'][0]['visual'] = '改过'
        self.assertEqual(sig, E.text_signature(o))

    def test_prompt(self):
        o = planned(3, ['split', 'diagram', 'bignum'], ['flow', 'loop', 'kpi'])
        cfg = E.load_project(tempfile.mkdtemp(prefix='did_cfg_'))
        d = {'name': 'D', 'light': 'Background: #FFFFFF', 'dark': 'Background: #000000', 'tone': {'content': 'light'}}
        tone, text = build_prompts.build(cfg, o, o['pages'][2], 3, len(o['pages']), d)
        self.assertIn('Draw it as: f2', text)
        self.assertIn('closed loop', text)
        self.assertIn('the previous slide (2) is two panels side by side', text)
        self.assertIn('the next slide (4) is one to three very large numbers', text)
        self.assertIn('Group 1 — draw as: 两个节点', text)
        self.assertIn('Diagram logic', text)
        quoted = re.findall(r'^\s*- [^:]+: "(.*)"$', text, re.M)
        self.assertEqual(quoted, [s for _, s in E.page_strings(o['pages'][2])])


class TestTextcheck(unittest.TestCase):
    def test_wrapped_in_column(self):
        try:
            import textcheck
        except ImportError:
            self.skipTest('Pillow not installed')
        box = lambda t, x0, y0: {'text': t, 'x0': x0, 'y0': y0, 'x1': x0 + 20 * len(t), 'y1': y0 + 34}
        lines = [box('约 10 万元，选款对照、', 70, 664), box('只给回搜率与商品访问', 440, 664),
                 box('调节演示、品牌核验、', 70, 703), box('跑赢的笔记加投，', 440, 698),
                 box('横评与售后四类', 70, 739), box('没有笔记跑赢就不投', 440, 737)]
        s = '约 10 万元，选款对照、调节演示、品牌核验、横评与售后四类'
        texts = [L['text'] for L in lines]
        self.assertLess(textcheck.best_ratio(s, texts), 0.8)                     # OCR order interleaves the columns
        self.assertEqual(textcheck.best_ratio(s, texts, textcheck.column_stacks(lines)), 1.0)

    def test_label_above_date(self):
        try:
            import textcheck
        except ImportError:
            self.skipTest('Pillow not installed')
        box = lambda t, x0, y0: {'text': t, 'x0': x0, 'y0': y0, 'x1': x0 + 30 * len(t), 'y1': y0 + 34}
        lines = [box('签约与准备', 40, 180), box('冷启动', 300, 180), box('9.24—10.11', 40, 218), box('10.12—11.8', 300, 218)]
        texts = [L['text'] for L in lines]
        s = '签约与准备 9.24—10.11'
        self.assertLess(textcheck.best_ratio(s, texts), 1.0)
        self.assertEqual(textcheck.best_ratio(s, texts, textcheck.column_stacks(lines)), 1.0)

    def test_no_page_number_corner_on_cover(self):
        try:
            import textcheck
        except ImportError:
            self.skipTest('Pillow not installed')
        cfg = E.load_project(tempfile.mkdtemp(prefix='did_cfg_'))
        self.assertTrue(E.page_number_on(cfg, 2, 15))
        self.assertFalse(E.page_number_on(cfg, 1, 15))
        self.assertFalse(E.page_number_on(cfg, 15, 15))
        self.assertIn('br', textcheck.corner_boxes(cfg, 1672, 941, True))
        self.assertNotIn('br', textcheck.corner_boxes(cfg, 1672, 941, False))
        self.assertEqual(build_prompts.reserved_corners(cfg, 1, 15), [])
        self.assertEqual(len(build_prompts.reserved_corners(cfg, 2, 15)), 1)


class TestHostos(unittest.TestCase):
    def test_runtime_paths(self):
        self.assertTrue(hostos.VENV_PY.startswith(hostos.RUNTIME))
        self.assertIn(hostos.ocr_backend(), ('vision', 'rapid'))

    def test_render_pdf_names(self):
        try:
            import pypdfium2  # noqa: F401
            from PIL import Image
        except ImportError:
            self.skipTest('pypdfium2 / Pillow not installed')
        d = tempfile.mkdtemp(prefix='did_pdf_')
        try:
            pdf = os.path.join(d, 'a.pdf')
            Image.new('RGB', (160, 90), 'white').save(pdf, save_all=True, append_images=[Image.new('RGB', (160, 90), 'black')] * 10)
            os.environ['DOC_IMAGE_DECK_PDF'] = 'pdfium'
            self.assertEqual(hostos.pdf_page_count(pdf), 11)
            outs = hostos.render_pdf(pdf, os.path.join(d, 'r'), size=(320, 180))
            self.assertEqual([os.path.basename(o) for o in outs[:2]], ['r-01.png', 'r-02.png'])
            self.assertEqual(Image.open(outs[0]).size, (320, 180))
            one = hostos.render_pdf(pdf, os.path.join(d, 's'), long_side=200, first=3, single=True)
            self.assertEqual(Image.open(one[0]).size[0], 200)
        finally:
            os.environ.pop('DOC_IMAGE_DECK_PDF', None)
            shutil.rmtree(d, ignore_errors=True)

    def test_windows_launcher(self):
        cmd = open(os.path.join(SCRIPTS, 'deck.cmd'), 'rb').read()
        self.assertIn(b'\r\n', cmd)                           # batch files need CRLF
        self.assertTrue(all(b < 128 for b in cmd))            # and plain ASCII
        self.assertNotIn(b'(\r\n  "%R%', cmd)                 # no %ERRORLEVEL% inside a parenthesised block


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
        import deck
        for script in list(deck.COMMANDS.values()) + [v[0] for v in deck.ANY_PYTHON.values()]:
            self.assertTrue(os.path.exists(os.path.join(SCRIPTS, script)), script)

    def test_python_compiles(self):
        import warnings
        for f in glob.glob(os.path.join(SCRIPTS, '**', '*.py'), recursive=True):
            with warnings.catch_warnings():
                warnings.simplefilter('error', SyntaxWarning)       # e.g. a Windows path with \\d in a docstring
                compile(open(f, encoding='utf-8').read(), f, 'exec')

    def test_no_client_material(self):
        names = [''.join(map(chr, cs)) for cs in ([0x68a6, 0x91d1, 0x56ed], [0x4e2d, 0x5174], [0x8d5b, 0x8bfa])]   # client names
        names.append('S' + 'inomax')
        banned = re.compile('|'.join(names + ['/Us' + 'ers/']), re.I)                             # and personal paths
        for f in glob.glob(os.path.join(ROOT, '**', '*'), recursive=True):
            f = f.replace(os.sep, '/')
            if '/private/' in f or '/.git/' in f or '__pycache__' in f or not os.path.isfile(f) or f.endswith(('.png', '.jpg')):
                continue
            text = open(f, encoding='utf-8', errors='ignore').read()
            self.assertIsNone(banned.search(text), f)


if __name__ == '__main__':
    unittest.main(verbosity=1, warnings='ignore')
