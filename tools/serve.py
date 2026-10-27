#!/usr/bin/env python3
"""ブラウザの下書き（index.html・reader.html。先に python3 tools/build.py で data/ を作る）を配る。
ブラウザにキャッシュさせない（スマホに古い app.js が残って画面が壊れるため）。

使い方: python3 tools/serve.py [port] [host]   （リポジトリのルートを配る。既定は 127.0.0.1:8765。
        スマホで見るときは host に 0.0.0.0 を渡す。リポジトリの全部が見えるので、信頼できるネットワークでだけ）
"""
import http.server
import os
import sys
from pathlib import Path


class NoCache(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()


def main():
    os.chdir(Path(__file__).resolve().parent.parent)
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    host = sys.argv[2] if len(sys.argv) > 2 else '127.0.0.1'
    http.server.ThreadingHTTPServer((host, port), NoCache).serve_forever()


if __name__ == '__main__':
    main()
