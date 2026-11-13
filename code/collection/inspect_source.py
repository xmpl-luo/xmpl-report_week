"""Save public evidence for editorial review; does not use account credentials."""
import argparse
import hashlib
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.http import request
from common.settings import RUNTIME, write_json, read_json
from collection.parsers import Page, sitemap_links


def inspect(url):
    path = RUNTIME / 'evidence' / (hashlib.sha256(url.encode()).hexdigest() + '.json')
    cached = read_json(path)
    if cached:
        result = {'url':url, 'saved':str(path), **cached.get('article',{})}
        if 'text' in result:
            result['text'] = result['text'][:9000]
        return result
    try:
        body = request(url, retries=0, timeout=25)
        if '.xml' in url:
            write_json(path, {'url':url,'html':body})
            try:
                nested, links = sitemap_links(body)
                return {'url':url,'saved':str(path),'nested':nested,'count':len(links),'links':links[:25]}
            except Exception:
                return {'url':url,'saved':str(path)}
        if body.lstrip().startswith(('[','{')):
            data = json.loads(body)
            write_json(path, {'url':url, 'data':data})
            if isinstance(data,list):
                return {'url':url,'saved':str(path),'posts':[{k:p.get(k) for k in ('title','post_date','canonical_url','slug')} for p in data]}
            return {'url':url, 'saved':str(path), 'keys':list(data)[:20]}
        article = Page(body,url).article()
        write_json(path, {'url':url,'html':body,'article':article})
        article['text'] = article['text'][:9000]
        return {'url':url,'saved':str(path), **article}
    except Exception as error:
        return {'url':url,'error':str(error)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('urls',nargs='+')
    args = parser.parse_args()
    with ThreadPoolExecutor(max_workers=4) as pool:
        for result in pool.map(inspect,args.urls):
            print(json.dumps(result,ensure_ascii=False),flush=True)

