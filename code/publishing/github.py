"""Export only project artifacts to an isolated clone; no force push or deletion."""
import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.settings import ROOT, RUNTIME, write_json

REMOTE = 'https://github.com/xmpl-luo/xmpl-report_week.git'
EXPORT = ['.gitignore', 'README.md', 'request.md', 'code', 'train_set', 'report_add', 'year']
EXCLUDED = {'.git', '.venv', '__pycache__', 'runtime', 'node_modules'}


def export_files():
    for name in EXPORT:
        path = ROOT/name
        if not path.exists():
            continue
        for item in ([path] if path.is_file() else path.rglob('*')):
            relative = item.relative_to(ROOT)
            if not item.is_file() or any(p in EXCLUDED for p in relative.parts):
                continue
            if item.name.startswith('.env') and item.name != '.env.example':
                continue
            if item.suffix in ('.pyc', '.log', '.cookies'):
                continue
            if item.is_symlink():
                raise ValueError('导出列表中包含符号链接，请先检查')
            text = item.read_text(encoding='utf-8-sig')
            if re.search(r'sk-[A-Za-z0-9_-]{20,}|/bot/v2/hook/[0-9a-f-]{20,}',text):
                raise ValueError(f'发现疑似密钥，拒绝导出：{relative}')
            if item.name == 'request.md':
                for line in text.splitlines():
                    if line.startswith('|'):
                        cells = [cell.strip() for cell in line.split('|')[1:-1]]
                        if len(cells) == 8 and cells[5] and not re.fullmatch(r'\*+|-+|密码',cells[5]):
                            raise ValueError('需求表存在未掩码密码，拒绝导出')
            yield item, relative


def publish(push=False):
    files = list(export_files())  # Validate before any network write.
    checkout = RUNTIME/'github_checkout'
    def git(*args, cwd=checkout, check=True):
        result = subprocess.run(['git','-c',f'safe.directory={cwd.as_posix()}',*args],cwd=cwd,capture_output=True,text=True,encoding='utf-8',errors='replace')
        if check and result.returncode:
            raise RuntimeError(f'Git命令失败：{args[0]}（退出码{result.returncode}）；请检查凭据、权限或Git作者身份')
        return result
    if not (checkout/'.git').exists():
        checkout.parent.mkdir(parents=True,exist_ok=True)
        git('clone',REMOTE,str(checkout),cwd=ROOT)
    remote = git('remote','get-url','origin').stdout.strip()
    if remote != REMOTE:
        raise ValueError('隔离仓库的origin与指定目标不同')
    if git('status','--porcelain').stdout.strip():
        raise ValueError('隔离仓库有未提交变更，请先检查，避免混入其他内容')
    if git('rev-parse','--verify','HEAD',check=False).returncode == 0:
        git('fetch','origin')
        if git('rev-parse','--verify','@{u}',check=False).returncode == 0:
            git('merge','--ff-only','@{u}')
    else:
        git('symbolic-ref','HEAD','refs/heads/main')
    # Check author configuration before copying files into the clone.
    git('var','GIT_AUTHOR_IDENT')
    names = []
    for source, relative in files:
        target = checkout/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source,target)
        names.append(relative.as_posix())
    git('add','--',*names)
    if git('diff','--cached','--quiet',check=False).returncode:
        git('commit','-m','Implement modular weekly reports and backfill 2026 weeks 36-39')
    commit = git('rev-parse','HEAD').stdout.strip()
    state = {'remote':REMOTE,'commit':commit,'file_count':len(names),'pushed':False}
    write_json(RUNTIME/'github_status.json',state)
    if push:
        git('push','-u','origin','HEAD')
        state['pushed'] = True
        write_json(RUNTIME/'github_status.json',state)
    return state


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='将允许的项目文件复制到隔离克隆、提交；--push才推送')
    parser.add_argument('--push',action='store_true')
    args = parser.parse_args()
    try:
        result = publish(args.push)
        print(f"提交完成：{result['commit']}；GitHub推送：{result['pushed']}")
    except (ValueError,RuntimeError,OSError) as error:
        print(str(error),file=sys.stderr)
        sys.exit(1)

