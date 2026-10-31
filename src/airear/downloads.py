"""Bounded HTTPS downloads with redirect host validation."""
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener


def validate_url(url: str, hosts: set[str]):
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in hosts or parsed.username or parsed.password:
        raise ValueError("허용되지 않은 다운로드 주소입니다.")
    return url


class SafeRedirect(HTTPRedirectHandler):
    def __init__(self, hosts):
        self.hosts = hosts

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_url(newurl, self.hosts)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch(url: str, hosts: set[str], limit: int = 2_000_000) -> bytes:
    validate_url(url, hosts)
    opener = build_opener(SafeRedirect(hosts))
    request = Request(url, headers={"User-Agent": "AirEar/1.0", "Accept": "application/json,*/*"})
    with opener.open(request, timeout=25) as response:
        result = response.read(limit + 1)
        if len(result) > limit:
            raise ValueError("다운로드 크기가 제한을 초과했습니다.")
        return result


def download(url: str, target: Path, hosts: set[str], limit: int, progress=None):
    # Stream large EXE without retaining a second full copy in memory.
    validate_url(url, hosts)
    opener = build_opener(SafeRedirect(hosts))
    total = 0
    try:
        with opener.open(Request(url, headers={"User-Agent": "AirEar/1.0"}), timeout=30) as response:
            length = response.headers.get('Content-Length')
            expected = int(length) if length and length.isdigit() else None
            if expected is not None and expected > limit:
                raise ValueError("다운로드 크기 제한 초과")
            if progress:
                progress(0, expected)
            with target.open("wb") as output:
                while chunk := response.read(1024 * 1024):
                    total += len(chunk)
                    if total > limit:
                        raise ValueError("다운로드 크기 제한 초과")
                    output.write(chunk)
                    if progress:
                        progress(total, expected)
            if expected is not None and total != expected:
                raise ValueError("다운로드 파일이 완전하지 않습니다.")
    except BaseException:
        target.unlink(missing_ok=True)
        raise
