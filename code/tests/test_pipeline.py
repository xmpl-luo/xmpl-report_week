import sys
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.periods import periods, previous_week, title_for
from collection.parsers import Page, feed_entries, published_day
from generation.render import render
from publishing.lark import checked, text_blocks, Lark
from collection.parsers import sitemap_links


class PipelineTests(unittest.TestCase):
    def test_four_historical_windows(self):
        windows = list(periods('20260830','20260926'))
        self.assertEqual(len(windows),4)
        self.assertEqual([title_for(*p) for p in windows], [f'2026第{n}周简报' for n in range(36,40)])

    def test_cross_year_iso_week(self):
        self.assertEqual(title_for(date(2025,12,29),date(2026,1,4)), '2026第01周简报')
        self.assertEqual(previous_week(date(2026,11,16)), (date(2026,11,9),date(2026,11,15)))

    def test_partial_window_rejected(self):
        with self.assertRaises(ValueError): list(periods('20260830','20260925'))

    def test_published_not_modified(self):
        page = Page('<script type="application/ld+json">{"@type":"BlogPosting","headline":"test","datePublished":"2026-09-01","dateModified":"2026-11-01"}</script><article><p>Hello</p></article>')
        self.assertEqual(page.article()['published'],'2026-09-01')
        self.assertEqual(page.article()['text'],'Hello')
        self.assertIsNone(Page('<meta property="article:modified_time" content="2026-09-01">').article()['published'])

    def test_rss_and_timezone(self):
        items = feed_entries('<rss><channel><item><title>One</title><link>https://example.com/a</link><pubDate>Sat, 05 Sep 2026 22:00:00 GMT</pubDate><description>&lt;p&gt;Body&lt;/p&gt;</description></item></channel></rss>','https://example.com')
        self.assertEqual(items[0]['published'],'2026-09-06')
        self.assertEqual(items[0]['text'],'Body')
        self.assertIsNone(published_day('not a date'))

    def test_atom_requires_original_publication(self):
        xml = '<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>A</title><link href="https://example.com/a"/><updated>2026-09-01</updated></entry></feed>'
        self.assertIsNone(feed_entries(xml,'https://example.com')[0]['published'])

    def test_empty_report_is_error(self):
        with self.assertRaises(ValueError): render(date(2026,9,1),date(2026,9,7),[],[])

    def test_remote_failures_not_success(self):
        with self.assertRaises(RuntimeError): checked({'code':999,'msg':'secret not echoed'})
        with self.assertRaises(RuntimeError): checked({'StatusCode':1})

    def test_block_heading_and_link(self):
        blocks = text_blocks('# Title\n\nhttps://example.com/a')
        self.assertEqual(blocks[0]['block_type'],3)
        self.assertEqual(blocks[1]['text']['elements'][0]['text_run']['text_element_style']['link']['url'],'https://example.com/a')

    def test_sitemap_ignores_image_locations(self):
        xml = '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:image="http://www.google.com/schemas/sitemap-image/1.1"><url><loc>https://example.com/post</loc><image:image><image:loc>https://example.com/image.png</image:loc></image:image></url></urlset>'
        self.assertEqual(sitemap_links(xml),(False,['https://example.com/post']))

    def test_podcast_date_is_dedicated_header(self):
        html = '<p>September 20, 2026</p><p data-testid="contributors-date">September 4, 2026</p>'
        self.assertEqual(Page(html,'https://www.gamedeveloper.com/production/test').article()['published'],'2026-09-04')
        self.assertIsNone(Page('<p>September 20, 2026</p>','https://www.gamedeveloper.com/production/test').article()['published'])

    def test_curated_reports_match_evidence_and_dates(self):
        from common.settings import CODE, ROOT, RUNTIME, read_json
        from common.periods import parse_date
        curated = read_json(CODE/'editorial/reviews/20260830-20260926.json')
        for start,end in periods('20260830','20260926'):
            selected = [e for e in curated['entries'] if start <= parse_date(e['published']) <= end]
            report = ROOT/'report_add/week'/f'{title_for(start,end)}.md'
            self.assertEqual(report.read_text(encoding='utf-8'),render(start,end,selected,curated['coverage']) if selected == sorted(selected,key=lambda e:(e['published'],e['url'])) else render(start,end,sorted(selected,key=lambda e:(e['published'],e['url'])),curated['coverage']))
        # Network snapshots are intentionally excluded from Git. If present,
        # verify summaries against the actually fetched publication metadata.
        evidence = {}
        for path in (RUNTIME/'http').glob('*.json'):
            data = read_json(path)
            if not any(x in data['url'] for x in ('feed','sitemap','format=')):
                evidence[data['url']] = Page(data['body'],data['url']).article()
        for path in (RUNTIME/'evidence').glob('*.json'):
            data = read_json(path)
            if data.get('article'):
                evidence[data['url']] = data['article']
        if evidence:
            for entry in curated['entries']:
                self.assertIn(entry['url'],evidence)
                self.assertEqual(evidence[entry['url']]['published'],entry['published'])

    def test_wiki_resume_does_not_duplicate(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'report.md'
            path.write_text('# Title\ncontent',encoding='utf-8')
            client = object.__new__(Lark)
            responses = [{'node':{'space_id':'space','node_token':'parent'}}, {'node':{'obj_token':'doc','node_token':'node'}},{}]
            with patch('publishing.lark.RUNTIME',Path(folder)), patch.object(client,'call',side_effect=responses) as call, patch('publishing.lark.time.sleep'):
                client.sync(path)
                client.sync(path)
                self.assertEqual(call.call_count,3)


if __name__ == '__main__': unittest.main()

