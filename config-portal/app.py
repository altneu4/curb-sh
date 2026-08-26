"""Curb circuit configuration portal.

A tiny, single-purpose web UI: list every circuit that's ever reported a
sample, and let someone flip whether its power reading should be displayed
inverted (for a CT clamp wired backwards, which reports negative watts for
real positive draw). Nothing else.

Deliberately not a general admin tool -- it connects to Postgres as the
`circuit_portal` role, which only has SELECT on circuit_config and UPDATE on
its invert_display column (see db/init/002_circuit_config.sh). Even a bug
here can't touch circuit_samples, group_samples, devices, or any other data,
because Postgres itself refuses it at the connection level, not because this
code happens to be careful.

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
  body { font-family: system-ui, sans-serif; max-width: 760px; margin: 2rem auto; padding: 0 1rem; color: #222; }
  h1 { font-size: 1.4rem; }
  p.help { color: #555; line-height: 1.4; }
  table { border-collapse: collapse; width: 100%; margin-top: 1rem; }
  th, td { text-align: left; padding: 0.5rem 0.75rem; border-bottom: 1px solid #ddd; }
  th { color: #555; font-weight: 600; font-size: 0.85rem; text-transform: uppercase; }
  .inverted { color: #b00020; font-weight: 600; }
  .normal { color: #1a7a1a; }
  form { margin: 0; }
  button {
    cursor: pointer; border: 1px solid #ccc; background: #f7f7f7;
    border-radius: 4px; padding: 0.35rem 0.7rem; font-size: 0.9rem;
  }
  button:hover { background: #eee; }
  .empty { color: #777; font-style: italic; margin-top: 1rem; }
</style>
<h1>Curb Circuit Configuration</h1>
<p class="help">
  Controls whether a circuit's power reading is shown inverted on the Curb
  dashboards -- for circuits with a CT clamp wired backwards, which always
  report negative watts for real positive draw. New circuits show up here
  automatically the first time they report a sample.
</p>
{% if rows %}
<table>
  <tr><th>Device</th><th>Group</th><th>Circuit</th><th>Display</th><th></th></tr>
  {% for row in rows %}
  <tr>
    <td>{{ row.serial_number }}</td>
    <td>{{ row.group_idx }}</td>
    <td>{{ row.circuit_idx }}</td>
    <td class="{{ 'inverted' if row.invert_display else 'normal' }}">
      {{ 'Inverted' if row.invert_display else 'Normal' }}
    </td>
    <td>
      <form method="post" action="{{ url_for('toggle') }}">
        <input type="hidden" name="serial_number" value="{{ row.serial_number }}">
        <input type="hidden" name="group_idx" value="{{ row.group_idx }}">
        <input type="hidden" name="circuit_idx" value="{{ row.circuit_idx }}">
        <button type="submit">
          {{ 'Set Normal' if row.invert_display else 'Set Inverted' }}
        </button>
      </form>
    </td>
  </tr>
  {% endfor %}
</table>
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
                "SELECT serial_number, group_idx, circuit_idx, invert_display "
                "FROM circuit_config "
                "ORDER BY serial_number, group_idx, circuit_idx"
            )
            cols = [d.name for d in cur.description]
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    finally:
        conn.close()
    return render_template_string(PAGE, rows=rows)


@app.route("/toggle", methods=["POST"])
def toggle():
    try:
        serial_number = request.form["serial_number"]
        group_idx = int(request.form["group_idx"])
        circuit_idx = int(request.form["circuit_idx"])
    except (KeyError, ValueError):
        abort(400)

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE circuit_config SET invert_display = NOT invert_display "
                "WHERE serial_number = %s AND group_idx = %s AND circuit_idx = %s",
                (serial_number, group_idx, circuit_idx),
            )
        conn.commit()
    finally:
        conn.close()
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
