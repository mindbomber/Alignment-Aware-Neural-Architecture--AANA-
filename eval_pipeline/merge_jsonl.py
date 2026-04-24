import argparse
import pathlib


def main():
    parser = argparse.ArgumentParser(description="Concatenate JSONL files.")
    parser.add_argument("--output", required=True)
    parser.add_argument("inputs", nargs="+")
    args = parser.parse_args()

    output = pathlib.Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with output.open("w", encoding="utf-8") as out:
        for input_path in args.inputs:
            with pathlib.Path(input_path).open("r", encoding="utf-8") as handle:
                for line in handle:
                    if line.strip():
                        out.write(line if line.endswith("\n") else line + "\n")
                        count += 1
    print(f"Wrote {count} rows to {output}")


if __name__ == "__main__":
    main()
