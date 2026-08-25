#!/usr/bin/env python3
"""
Patches ONLY the "endpoints" section of a Curb device's hub-config.json to
point at a curb-selfhosted receiver -- everything else (sensor calibration,
hub_id, location_id, sampling/load_control settings) is left untouched.

Deliberately does not run on the device itself -- BusyBox/Buildroot images
like the Curb's don't reliably have a JSON tool (jq or similar) available,
and this device's config is small enough that round-tripping it through
your own machine, where you have real tooling, is simpler and safer than
guessing what's on the device. Stdlib only, no dependencies.

Usage:

  1. Pull the device's current config down (see docs/SETUP.md for the
     scp -O background):

       scp -O -o HostKeyAlgorithms=+ssh-rsa -o PubkeyAcceptedAlgorithms=+ssh-rsa \\
           root@<curb-ip>:/data/hub-config.json ./hub-config.json

  2. Patch it locally -- this overwrites ./hub-config.json in place and
     keeps the untouched original alongside it as hub-config.json.bak:

       python3 apply_endpoint_patch.py --input hub-config.json --host 192.168.1.50:8080

  3. Push the patched file back (no remount dance needed -- /data is
     mounted read-write) and force an immediate restart rather than
     waiting up to 10 minutes for streamer.lua's own reconnect timeout:

       scp -O -o HostKeyAlgorithms=+ssh-rsa -o PubkeyAcceptedAlgorithms=+ssh-rsa \\
           ./hub-config.json root@<curb-ip>:/data/hub-config.json
       ssh -o HostKeyAlgorithms=+ssh-rsa -o PubkeyAcceptedAlgorithms=+ssh-rsa root@<curb-ip> \\
           "ps | grep streamer"
       # then, over the same ssh session: kill <pid>   (hm respawns it in ~2s)

DO NOT just copy examples/hub-config.after.example.json over your device's
real file -- that example's sensor calibration values are fabricated
placeholders, not your device's real ones, and overwriting them will break
your actual readings. This script patches your device's real file in
place; the example files are for reference only.
"""

import argparse
import json
import shutil
import sys


def build_endpoints(host: str, scheme: str) -> dict:
    base = f"{scheme}://{host}"
    return {
        "hub_config": f"{base}/v3/hub_config",
        "messages": f"{base}/v3/messages",
        "samples": f"{base}/v3/samples",
        "diagnostics": f"{base}/v3/diagnostics",
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--input", required=True, help="Path to the device's downloaded hub-config.json")
    parser.add_argument("--host", required=True, help="Receiver host:port, e.g. 192.168.1.50:8080")
    parser.add_argument(
        "--scheme", default="http", choices=["http", "https"],
        help="Defaults to http -- see docs/SETUP.md for why plain HTTP is the recommended path "
             "(the device's streamer code verifies TLS certs and there's no override for it)",
    )
    parser.add_argument(
        "--output", default=None,
        help="Defaults to overwriting --input (the untouched original is kept as <input>.bak)",
    )
    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
        config = json.load(f)

    if "revision" not in config:
        print(
            "ERROR: input file has no 'revision' field -- this doesn't look like a real "
            "hub-config.json (the device's config.lua requires this field to exist and "
            "falls back to defaults without it).",
            file=sys.stderr,
        )
        sys.exit(1)

    original_endpoints = config.get("endpoints", {})
    config["endpoints"] = build_endpoints(args.host, args.scheme)

    output_path = args.output or args.input
    if output_path == args.input:
        backup_path = args.input + ".bak"
        shutil.copy2(args.input, backup_path)
        print(f"Backed up original to {backup_path}")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
        f.write("\n")

    print(f"Wrote {output_path}")
    print("\nEndpoints changed:")
    for key in sorted(set(original_endpoints) | set(config["endpoints"])):
        old = original_endpoints.get(key, "<none>")
        new = config["endpoints"][key]
        if old != new:
            print(f"  {key}:")
            print(f"    - {old}")
            print(f"    + {new}")

    print(
        "\nEverything else in the file (sensors, hub_id, location_id, sampling, "
        "load_control) was left exactly as it was."
    )


if __name__ == "__main__":
    main()
