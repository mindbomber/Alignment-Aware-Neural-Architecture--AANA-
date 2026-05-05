#!/usr/bin/env python
"""Build public family-pack landing pages for AANA adapters."""

import argparse
import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from eval_pipeline import adapter_gallery, family_packs


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build AANA family-pack landing pages.")
    parser.add_argument("--gallery", default=str(adapter_gallery.DEFAULT_GALLERY), help="Adapter gallery JSON.")
    parser.add_argument("--output-root", default=str(ROOT / "docs"), help="Output docs root.")
    args = parser.parse_args(argv)
    gallery_payload = adapter_gallery.published_gallery(gallery_path=args.gallery)
    payload = family_packs.write_family_pages(output_root=args.output_root, gallery_payload=gallery_payload)
    families = ", ".join(pack["slug"] for pack in payload["families"])
    print(f"Wrote {len(payload['families'])} AANA family page(s): {families}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
