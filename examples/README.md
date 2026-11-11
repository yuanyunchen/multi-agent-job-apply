# examples/ — see it work, offline, in a few seconds

Every script here runs **completely offline** against synthetic data: made-up
companies, made-up postings, a made-up mailbox. None of them reads your
settings, touches your records, opens a browser, or sends anything. They exist
so you can watch each piece work before you trust it with anything real.

Each one writes its own throwaway data directory under your system's temporary
folder and prints what it did.

```bash
pip install -e .        # from the project root
python examples/search_dry_run.py
```

| script | what it shows |
|---|---|
| [`01_setup_dry_run.sh`](01_setup_dry_run.sh) | the whole first conversation, answered from a file, writing settings to a throwaway folder |
| [`search_dry_run.py`](search_dry_run.py) | one search pass over fixture job pages, with de-duplication |
| [`screen_and_tier.py`](screen_and_tier.py) | reading descriptions: what is kept, what is dropped, and the sentence that dropped it |
| [`rank_queue.py`](rank_queue.py) | the order applications go out in, and how deep the list is |
| [`apply_dry_run.py`](apply_dry_run.py) | a practice run through the list: nothing claimed, nothing sent |
| [`digest_preview.py`](digest_preview.py) | the one summary a day, as the user would read it |
| [`reflection_preview.py`](reflection_preview.py) | the end-of-day look back, and the suggestions it produces |
| [`read_email_code_demo.py`](read_email_code_demo.py) | reading a verification code from a fake mailbox, and every case where it refuses |

`tests/test_examples.py` runs all of them, so an example that stops working
fails the build rather than quietly rotting.
