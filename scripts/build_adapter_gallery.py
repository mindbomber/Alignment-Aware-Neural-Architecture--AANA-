#!/usr/bin/env python
"""Build the public searchable adapter gallery data file."""

import argparse
import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from eval_pipeline import adapter_gallery


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build public AANA adapter gallery data.")
    parser.add_argument("--gallery", default=str(adapter_gallery.DEFAULT_GALLERY), help="Adapter gallery JSON.")
    parser.add_argument("--output", default=str(ROOT / "docs" / "adapter-gallery" / "data.json"), help="Output JSON path.")
    args = parser.parse_args(argv)
    payload = adapter_gallery.write_published_gallery(args.output, gallery_path=args.gallery)
    print(f"Wrote {args.output} with {payload['adapter_count']} adapters.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
