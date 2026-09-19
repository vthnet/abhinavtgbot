def fmt_curr(amount):
    """Format an INR amount with the Indian currency symbol and commas."""
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        return "₹0"

    if amount.is_integer():
        return f"₹{int(amount):,}"

    return f"₹{amount:,.2f}"