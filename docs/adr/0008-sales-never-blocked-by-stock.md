# Sales are never blocked by stock

A sale goes through even when the SKU's System Quantity is zero (typically because its Goods Receipt hasn't been entered yet); the SKU goes into Negative Stock and is flagged on the Owner's dashboard. COGS for the oversold quantity uses the SKU's latest unit cost and is not restated when the goods arrive. Blocking the sale was rejected: turning a paying customer away is worse than a flagged discrepancy that the next Stock Opname resolves anyway.
