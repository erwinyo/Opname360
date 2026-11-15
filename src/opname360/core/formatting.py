"""How values are written in messages shown to staff (Indonesian)."""


def rupiah(amount: int) -> str:
    """1250000 -> 'Rp 1.250.000'."""
    return 'Rp ' + f'{amount:,}'.replace(',', '.')


def sku_label(product_name: str, size: str | None, color: str | None) -> str:
    """'Kemeja Putih SD (10, Putih)', or just the name without variants."""
    variant = ', '.join(part for part in (size, color) if part)
    return f'{product_name} ({variant})' if variant else product_name
