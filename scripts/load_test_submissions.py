"""
Load test for the public submissions endpoint.

Usage:
    python scripts/load_test_submissions.py --token <campaign_token> [options]

Options:
    --token         Campaign token (required)
    --role-id       A valid role ID for fixed-role submissions (required unless --other-only)
    --url           Base URL of the running server (default: http://localhost:8000)
    --count         Total number of requests to send (default: 100)
    --concurrency   Number of concurrent worker threads (default: 20)
    --other-only    Send only other-role submissions

Example:
    python scripts/load_test_submissions.py --token abc123 --role-id 1 --count 100 --concurrency 20
"""

import argparse
import io
import json
import statistics
import threading
import time
from dataclasses import dataclass, field
from typing import Optional

try:
    import requests
except ImportError:
    raise SystemExit("Install requests first:  pip install requests")


@dataclass
class Result:
    status_code: int
    elapsed_ms: float
    is_duplicate: bool = False
    error: Optional[str] = None


def _make_resume_bytes() -> bytes:
    return b'%PDF-1.4 1 0 obj << /Type /Catalog >> endobj'


def _submit(base_url: str, token: str, role_id: Optional[int], idx: int, results: list):
    """Send one submission request and record the result."""
    unique = idx % 2 == 0          # even → unique mobile; odd → repeat mobile 0000000001
    mobile = f'98765{str(idx).zfill(5)}' if unique else '9876500001'
    use_other = role_id is None or (idx % 5 == 4)  # every 5th request uses other-role

    payload = {
        'campaign_token': token,
        'first_name': 'Load',
        'last_name': f'Test{idx}',
        'mobile_number': mobile,
        'language': 'en',
        'answers': json.dumps([]),
    }
    if use_other:
        payload['other_role_title'] = 'Electrician' if idx % 2 == 0 else 'Plumber'
        payload['role_id'] = ''
    else:
        payload['role_id'] = str(role_id)
        payload['other_role_title'] = ''

    resume_file = io.BytesIO(_make_resume_bytes())
    resume_file.name = 'resume.pdf'
    files = {'resume': ('resume.pdf', resume_file, 'application/pdf')}

    url = f'{base_url.rstrip("/")}/api/public/submissions/'
    t0 = time.perf_counter()
    try:
        resp = requests.post(url, data=payload, files=files, timeout=30)
        elapsed = (time.perf_counter() - t0) * 1000
        is_dup = False
        if resp.status_code == 201:
            try:
                is_dup = resp.json().get('is_possible_duplicate', False)
            except Exception:
                pass
        results[idx] = Result(status_code=resp.status_code, elapsed_ms=elapsed, is_duplicate=is_dup)
    except Exception as exc:
        elapsed = (time.perf_counter() - t0) * 1000
        results[idx] = Result(status_code=0, elapsed_ms=elapsed, error=str(exc))


def run_load_test(base_url: str, token: str, role_id: Optional[int],
                  count: int, concurrency: int) -> None:
    results = [None] * count
    sem = threading.Semaphore(concurrency)

    def worker(idx):
        with sem:
            _submit(base_url, token, role_id, idx, results)

    print(f"\nLoad test: {count} requests, concurrency={concurrency}, target={base_url}")
    print('-' * 60)

    t_start = time.perf_counter()
    threads = [threading.Thread(target=worker, args=(i,)) for i in range(count)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    total_elapsed_s = time.perf_counter() - t_start

    success = [r for r in results if r and r.status_code == 201]
    errors = [r for r in results if r and (r.status_code == 0 or r.status_code >= 500)]
    client_errors = [r for r in results if r and 400 <= r.status_code < 500]
    duplicates = [r for r in success if r.is_duplicate]
    timings = [r.elapsed_ms for r in results if r and r.elapsed_ms]

    print(f"Total requests:      {count}")
    print(f"Success (201):       {len(success)}")
    print(f"Client errors (4xx): {len(client_errors)}")
    print(f"Server errors (5xx): {len(errors)}")
    print(f"Possible duplicates: {len(duplicates)}")
    print(f"Created submissions: {len(success) - len(duplicates)}")

    if timings:
        timings_sorted = sorted(timings)
        p95_idx = int(len(timings_sorted) * 0.95)
        print(f"\nResponse times (ms):")
        print(f"  Average:  {statistics.mean(timings):.1f}")
        print(f"  Median:   {statistics.median(timings):.1f}")
        print(f"  P95:      {timings_sorted[min(p95_idx, len(timings_sorted) - 1)]:.1f}")
        print(f"  Min/Max:  {min(timings):.1f} / {max(timings):.1f}")

    print(f"\nWall time: {total_elapsed_s:.2f}s  ({count / total_elapsed_s:.1f} req/s)")

    if errors:
        print(f"\nFirst server error: {errors[0]}")


def main():
    parser = argparse.ArgumentParser(description='Load test the public submissions endpoint.')
    parser.add_argument('--token', required=True, help='QRCampaign token')
    parser.add_argument('--role-id', type=int, default=None, help='Fixed role ID')
    parser.add_argument('--url', default='http://localhost:8000', help='Server base URL')
    parser.add_argument('--count', type=int, default=100, help='Total requests')
    parser.add_argument('--concurrency', type=int, default=20, help='Concurrent workers')
    parser.add_argument('--other-only', action='store_true', help='Use only other-role submissions')
    args = parser.parse_args()

    role_id = None if args.other_only else args.role_id
    if not args.other_only and role_id is None:
        parser.error('--role-id is required unless --other-only is set')

    run_load_test(args.url, args.token, role_id, args.count, args.concurrency)


if __name__ == '__main__':
    main()
