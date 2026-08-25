# Examples

Reference files for pointing a Curb device at your receiver. See
[`../docs/SETUP.md`](../docs/SETUP.md) for the full walkthrough -- this
folder is the supporting material for that doc, not a replacement for it.

| File | What it's for |
|---|---|
| `hub-config.before.example.json` | What a device's `/data/hub-config.json` looks like out of the box (fabricated calibration values, real structure) -- endpoints pointed at Curb's dead cloud. |
| `hub-config.after.example.json` | The same file after pointing it at a receiver -- only the `endpoints` block differs. Diff them yourself to see exactly what changes and what doesn't. |
| `endpoints-patch.json` | Just the `endpoints` fragment, if you'd rather hand-edit your device's real file directly and want something to copy from. |
| `apply_endpoint_patch.py` | A stdlib-only script that applies that same patch to a real downloaded config automatically, backing up the original first. Recommended over hand-editing. |

## Important: these example files are not your device's config

`hub-config.before.example.json` and `hub-config.after.example.json` use
**fabricated sensor calibration values** -- they exist to show you the
shape of the file and exactly what a correct endpoint patch looks like, not
to be copied onto a real device. Every Curb's `sensors` block is
individually calibrated at the factory; overwriting your device's real
`hub-config.json` with one of these example files will replace your actual
calibration with garbage and your readings will be wrong.

The safe path is always: pull your device's *real* `hub-config.json` down,
patch only the `endpoints` block (by hand using `endpoints-patch.json` as a
reference, or automatically with `apply_endpoint_patch.py`), then push that
same file back. Full steps in [`../docs/SETUP.md`](../docs/SETUP.md).
