# Contributing

This list ranks Grok trackers by the plan that actually includes Grok, not by the price on the front of the pricing page. Corrections are the most useful contribution, because vendor pricing moves every few months.

## Change the data, then regenerate

1. Edit [tools.yaml](tools.yaml). Fields: `name`, `url`, `currency`, `entry_price`, `entry_plan`, `grok_price` (or `null`), `grok_plan`, `grok_confirmed`, `refresh`, `trial`, `best_for`.
2. Do not add a premium field. `render_table.py` computes the Grok premium from `grok_price` and `entry_price`.
3. Run `python render_table.py --write`, then `python render_table.py --check`.
4. Open a pull request with a link to the vendor page that shows the new price or plan.

## Accepted

- A price change, with the plan name and whether it is monthly or yearly.
- Proof that Grok is or is not on a named plan. Set `grok_confirmed: false` when the vendor lists Grok in general but not on that plan.
- A new tool, if its own pricing page names Grok somewhere.

## Not accepted

- Affiliate or tracking links. Use the vendor's own domain.
- Review scores or star ratings. They change the subject from coverage to opinion.
- Currency conversions. Keep the currency the vendor publishes.

## Setup

```bash
pip install pyyaml
python render_table.py              # preview
python render_table.py --write      # write the table into README.md
python render_table.py --check      # what CI runs
python render_table.py --budget 100 # Grok plans at or under a monthly budget
python -m unittest discover -s tests # tracker tests, no network, no API key
```

## Tracker changes

The tracker under `tracker/` stays standard library only and must run on Python 3.9. Parse logic belongs in `parse.py` as pure functions with a test in `tests/test_tracker.py`. If xAI changes the Responses API shape, update `examples/sample-response.json` from the official docs first, then the parser.
