"""Curb circuit configuration portal.

A tiny, single-purpose web UI: list every circuit that's ever reported a
sample, one row each, with a single Save button per row that commits all
four settings for that circuit together:
  - a friendly label (shown on the dashboards in place of "Group X Circuit Y")
  - its breaker's rated amperage (feeds a "% of breaker capacity" panel)
  - whether it's a 240V circuit monitored by a single-leg clamp (doubles the
    computed watts/kWh/cost to correct for the un-clamped leg)
  - whether its power reading should be displayed inverted (for a CT clamp
    wired backwards, which reports negative watts for real positive draw)
One button per row rather than one per field, and no page-wide Save --
matches the real workflow of standing at the breaker panel with one circuit
at a time, and means nothing typed is lost if the page is closed mid-walk.
Nothing else.

Deliberately not a general admin tool -- it connects to Postgres as the
`circuit_portal` role, which only has SELECT on circuit_config and UPDATE on
these four columns specifically (see db/init/002_circuit_config.sh,
db/init/003_circuit_label.sql, and db/init/004_circuit_electrical.sql). Even
a bug here can't touch circuit_samples, group_samples, devices, or any other
data, because Postgres itself refuses it at the connection level, not
because this code happens to be careful.

No login -- same trust model as Grafana and the receiver in this stack:
reachable only on your LAN, not exposed to the internet. If that ever
changes for your deployment, put this behind a reverse proxy with auth
rather than relying on this app to add its own.
"""

import os

from flask import Flask, abort, redirect, render_template_string, request, url_for
import psycopg2

app = Flask(__name__)


def get_conn():
    return psycopg2.connect(
        host=os.environ["POSTGRES_HOST"],
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["PORTAL_DB_USER"],
        password=os.environ["PORTAL_DB_PASSWORD"],
    )


PAGE = """
<!doctype html>
<title>Curb Circuit Configuration</title>
<style>
  body { font-family: system-ui, sans-serif; max-width: 860px; margin: 2rem auto; padding: 0 1rem; color: #222; }
  h1 { font-size: 1.4rem; }
  p.help { color: #555; line-height: 1.4; }
  table { border-collapse: collapse; width: 100%; margin-top: 1rem; }
  th, td { text-align: left; padding: 0.5rem 0.75rem; border-bottom: 1px solid #ddd; }
  th { color: #555; font-weight: 600; font-size: 0.85rem; text-transform: uppercase; }
  input[type=text], input[type=number] {
    border: 1px solid #ccc; border-radius: 4px; padding: 0.35rem 0.5rem;
    font-size: 0.9rem;
  }
  input[type=text] { width: 10rem; }
  input[type=number] { width: 5rem; }
  input[type=checkbox] { width: 1.1rem; height: 1.1rem; }
  button {
    cursor: pointer; border: 1px solid #ccc; background: #f7f7f7;
    border-radius: 4px; padding: 0.35rem 0.7rem; font-size: 0.9rem;
    white-space: nowrap;
  }
  button:hover { background: #eee; }
  .empty { color: #777; font-style: italic; margin-top: 1rem; }
  table { table-layout: auto; }
</style>
<h1>Curb Circuit Configuration</h1>
<p class="help">
  Set a friendly label for each circuit (shown on the dashboards in place of
  "Group X Circuit Y"), its breaker's rated amperage (feeds a "% of breaker
  capacity" panel), whether a 240V circuit is monitored by a single-leg
  clamp (doubles the computed power to correct for the un-clamped leg), and
  whether its power reading should be displayed inverted (for a CT clamp
  wired backwards, which always reports negative watts for real positive
  draw). New circuits show up here automatically the first time they report
  a sample.
</p>
{% if rows %}
<div style="overflow-x: auto;">
{% for row in rows %}
<form id="row-{{ loop.index }}" method="post" action="{{ url_for('save') }}"></form>
{% endfor %}
<table>
  <tr>
    <th>Device</th><th>Group</th><th>Circuit</th><th>Label</th>
    <th>Breaker (A)</th><th>240V, 1 clamp</th><th>Inverted</th><th></th>
  </tr>
  {% for row in rows %}
  <tr>
    <td>{{ row.serial_number }}</td>
    <td>{{ row.group_idx }}</td>
    <td>{{ row.circuit_idx }}</td>
    <td>
      <input type="hidden" form="row-{{ loop.index }}" name="serial_number" value="{{ row.serial_number }}">
      <input type="hidden" form="row-{{ loop.index }}" name="group_idx" value="{{ row.group_idx }}">
      <input type="hidden" form="row-{{ loop.index }}" name="circuit_idx" value="{{ row.circuit_idx }}">
      <input type="text" form="row-{{ loop.index }}" name="label" value="{{ row.label or '' }}" placeholder="e.g. Kitchen" maxlength="100">
    </td>
    <td>
      <input type="number" form="row-{{ loop.index }}" name="breaker_amps" value="{{ row.breaker_amps or '' }}" placeholder="e.g. 20" min="1" step="1">
    </td>
    <td style="text-align: center;">
      <input type="checkbox" form="row-{{ loop.index }}" name="is_240v_single_clamp" {{ 'checked' if row.is_240v_single_clamp }}>
    </td>
    <td style="text-align: center;">
      <input type="checkbox" form="row-{{ loop.index }}" name="invert_display" {{ 'checked' if row.invert_display }}>
    </td>
    <td>
      <button type="submit" form="row-{{ loop.index }}">Save</button>
    </td>
  </tr>
  {% endfor %}
</table>
</div>
<p class="help" style="margin-top: 1rem;">
  Each row saves independently -- there's no page-wide Save, so nothing is
  lost if you close this partway through a walk around the breaker panel.
</p>
{% else %}
<p class="empty">No circuits reported yet -- once your device starts sending samples, they'll appear here.</p>
{% endif %}
"""


@app.route("/")
def index():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT serial_number, group_idx, circuit_idx, invert_display, label, "
                "       breaker_amps, is_240v_single_clamp "
                "FROM circuit_config "
                "ORDER BY serial_number, group_idx, circuit_idx"
            )
            cols = [d.name for d in cur.description]
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    finally:
        conn.close()
    return render_template_string(PAGE, rows=rows)


@app.route("/save", methods=["POST"])
def save():
    """One row, one commit: label, breaker amperage, and both flags together.

    Deliberately not per-field -- the real workflow is standing at the
    breaker panel with one circuit in front of you, setting whatever's known
    about it right then. A checkbox absent from the submitted form means
    unchecked (plain HTML behavior), so this is a SET of both flags to
    exactly what the form showed, not a toggle -- simpler to reason about
    once multiple fields share one submit.
    """
    try:
        serial_number = request.form["serial_number"]
        group_idx = int(request.form["group_idx"])
        circuit_idx = int(request.form["circuit_idx"])
    except (KeyError, ValueError):
        abort(400)

    # Blank label clears it (falls back to "Group X Circuit Y" on the
    # dashboards) rather than storing an empty string.
    label = request.form.get("label", "").strip() or None

    # Blank breaker_amps clears it (the capacity panel just shows no data
    # for this circuit until it's set again) rather than storing a 0 or
    # negative value -- the database's own CHECK constraint would reject
    # those anyway, but validating here gives a cleaner error than a raw SQL
    # failure.
    raw_amps = request.form.get("breaker_amps", "").strip()
    if raw_amps == "":
        breaker_amps = None
    else:
        try:
            breaker_amps = float(raw_amps)
        except ValueError:
            abort(400)
        if breaker_amps <= 0:
            abort(400)

    invert_display = "invert_display" in request.form
    is_240v_single_clamp = "is_240v_single_clamp" in request.form

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE circuit_config "
                "SET label = %s, breaker_amps = %s, invert_display = %s, is_240v_single_clamp = %s "
                "WHERE serial_number = %s AND group_idx = %s AND circuit_idx = %s",
                (
                    label, breaker_amps, invert_display, is_240v_single_clamp,
                    serial_number, group_idx, circuit_idx,
                ),
            )
        conn.commit()
    finally:
        conn.close()
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
