Release type: minor

Added a new optional constructor parameter to always use lists instead of relay Connections for relationships. Defaults to False, maintaining current functionality. If set to True, all relationships will be handled as lists.

Example:
mapper = StrawberrySQLAlchemyMapper(always_use_list=True)
