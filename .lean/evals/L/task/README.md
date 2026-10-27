# Task

Issue: the monthly expense report is wrong for some inputs. `data/sample.csv` produces the wrong
category totals and `report.format_report` output does not match `data/expected.txt`. Find and fix the
cause(s) in the `report` package. Keep the public functions and their signatures.

Report rules (from the finance team):
- Amounts may use `,` as a thousands separator (`1,234.50`) and parentheses for negatives (`(12.00)` is -12.00);
  a leading `-` is also a negative. Blank amounts are invalid (`ValueError`).
- Totals are exact to the cent: no floating-point drift.
- Report lines are `<category>: <total>` sorted by category, totals with two decimals and thousands separators,
  negatives as `-1,234.50`, followed by a final `TOTAL: <grand total>` line. Displayed values are rounded to the
  cent, half away from zero (`1.005` shows `1.01`, `-1.005` shows `-1.01`); `TOTAL` is the exact sum of all
  amounts, rounded once.

`python3 -m unittest discover -s tests` runs the visible tests.
