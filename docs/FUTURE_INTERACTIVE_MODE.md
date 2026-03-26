# Future Enhancement: Interactive Questionnaire

## Goal
Add `python3 main.py new-questionnaire --interactive` that walks the user through each field:
- **Multiple choice fields** (primary_goal, tone, etc.): Arrow key selection menu
- **Free text fields** (email_theme, key_message, etc.): Type freely
- **Number fields** (num_featured_products): Validate 1-6 range
- **Boolean fields** (generate_discount_code): Y/n prompt

## Implementation
Use `questionary` library (lightweight, good UX):
```bash
pip install questionary
```

Example interactive flow:
```python
import questionary

primary_goal = questionary.select(
    "What is the primary goal?",
    choices=["drive_sales", "clear_inventory", "introduce_new_product", "re_engage", "announce_promotion"]
).ask()

email_theme = questionary.text(
    "What is this email about? (be descriptive)"
).ask()
```

## Benefits
- No more validation errors from typos
- Faster than editing YAML
- Shows available options inline
- Still outputs YAML file for editing/reuse

## Status
📝 Documented for future implementation (not blocking current pipeline work)
